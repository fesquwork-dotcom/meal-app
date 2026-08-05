"""CLI: python -m recipes.cli import|report|select|evaluate|quality-audit|source-review|source-compare|planner-readiness|diversity-report|plan-week|diagnose-plan"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import yaml

from recipes.catalog_report import build_catalog_report, log_catalog_report
from recipes.diversity_report import (
    DEFAULT_REPORT_PATH as DIVERSITY_DEFAULT_PATH,
    run_diversity_report,
)
from recipes.enums import BudgetClass, GoalType, MealType, ProteinSourceTag
from recipes.evaluation.engine import CatalogEvaluator
from recipes.evaluation.report_format import format_console_report, format_markdown_report
from recipes.importer import RecipeCatalogImporter
from recipes.planner_readiness import (
    DEFAULT_REPORT_PATH as PLANNER_DEFAULT_PATH,
    run_planner_readiness,
)
from recipes.quality.audit import RecipeQualityAuditor
from recipes.quality.enums import SourceType
from recipes.quality.report import format_quality_summary
from recipes.quality.source_comparison import RecipeSourceComparison
from recipes.quality.source_draft import SourceBackedDraftBuilder
from recipes.quality.source_models import (
    IngredientObservation,
    RecipeConcept,
    RecipeSourceObservation,
)
from recipes.quality.source_review import RecipeSourceReviewer
from recipes.repository import RecipeRepository
from recipes.selection.codes import reason_text_ru
from recipes.selection.context import CandidateSelectionContext
from recipes.selection.selector import RecipeCandidateSelector


def _parse_budget_list(raw: str | None) -> list[BudgetClass] | None:
    if not raw:
        return None
    return [BudgetClass(part.strip()) for part in raw.split(",") if part.strip()]


def _parse_proteins(raw: str | None) -> set[ProteinSourceTag]:
    if not raw:
        return set()
    return {ProteinSourceTag(part.strip()) for part in raw.split(",") if part.strip()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Recipe Catalog tools")
    sub = parser.add_subparsers(dest="command", required=True)

    imp = sub.add_parser("import", help="Import catalog into SQLite")
    imp.add_argument(
        "--mode",
        choices=["dry_run", "validate_only", "upsert", "replace_catalog"],
        default="upsert",
    )
    imp.add_argument("--catalog-root", default=None)
    imp.add_argument("--db", default=None)

    rep = sub.add_parser("report", help="Print catalog coverage report")
    rep.add_argument("--db", default=None)
    rep.add_argument("--catalog-root", default=None)
    rep.add_argument("--json", action="store_true")

    sel = sub.add_parser("select", help="Debug recipe candidate selection")
    sel.add_argument("--meal-type", required=True, choices=[m.value for m in MealType])
    sel.add_argument("--goal", default=None, choices=[g.value for g in GoalType])
    sel.add_argument("--max-time", type=int, default=None)
    sel.add_argument("--limit", type=int, default=5)
    sel.add_argument("--budget-classes", default=None)
    sel.add_argument("--exclude-protein", default=None)
    sel.add_argument("--prefer-protein", default=None)
    sel.add_argument("--batch", action="store_true")
    sel.add_argument("--leftovers", action="store_true")
    sel.add_argument("--family", action="store_true")
    sel.add_argument("--db", default=None)
    sel.add_argument("--json", action="store_true")

    eva = sub.add_parser("evaluate", help="Catalog coverage evaluation")
    eva.add_argument("--scenario-file", default=None)
    eva.add_argument("--group", default=None)
    eva.add_argument("--db", default=None)
    eva.add_argument("--json", action="store_true")
    eva.add_argument("--show-critical", action="store_true")
    eva.add_argument("--show-recommendations", action="store_true")
    eva.add_argument("--output", default=None)

    qa = sub.add_parser("quality-audit", help="Recipe quality & provenance audit")
    qa.add_argument("--db", default=None)
    qa.add_argument("--json", action="store_true")
    qa.add_argument("--output", default=None, help="Markdown report path")
    qa.add_argument("--recipe-id", default=None)
    qa.add_argument(
        "--apply",
        action="store_true",
        help="Allow raise to computationally_checked only",
    )
    qa.add_argument("--show-blocking", action="store_true")
    qa.add_argument("--show-recommendations", action="store_true")
    qa.add_argument("--show-unverified", action="store_true")

    sr = sub.add_parser(
        "source-review",
        help="Compare a catalog recipe to structured source observations (JSON/YAML)",
    )
    sr.add_argument("recipe_id")
    sr.add_argument(
        "--observations",
        required=True,
        help="Path to JSON/YAML list of RecipeSourceObservation payloads",
    )
    sr.add_argument("--db", default=None)
    sr.add_argument("--json", action="store_true")

    sc = sub.add_parser(
        "source-compare",
        help="Compare observations and build a SourceBackedRecipeDraft",
    )
    sc.add_argument(
        "--concept",
        required=True,
        help="Path to JSON/YAML RecipeConcept payload",
    )
    sc.add_argument(
        "--observations",
        required=True,
        help="Path to JSON/YAML list of RecipeSourceObservation payloads",
    )
    sc.add_argument("--json", action="store_true")

    pr = sub.add_parser(
        "planner-readiness",
        help="Weekly Planner readiness metrics (Sprint 10.9)",
    )
    pr.add_argument("--db", default=None)
    pr.add_argument(
        "--output",
        default=None,
        help=f"Markdown path (default: {PLANNER_DEFAULT_PATH})",
    )
    pr.add_argument("--json", action="store_true")

    div = sub.add_parser(
        "diversity-report",
        help="Catalog diversity distribution report (Sprint 10.9)",
    )
    div.add_argument("--db", default=None)
    div.add_argument(
        "--output",
        default=None,
        help=f"Markdown path (default: {DIVERSITY_DEFAULT_PATH})",
    )
    div.add_argument("--json", action="store_true")

    pw = sub.add_parser(
        "plan-week",
        help="Deterministic Weekly Recipe Planner v1 (Sprint 10.10)",
    )
    pw.add_argument("--days", type=int, default=7)
    pw.add_argument(
        "--meal-types",
        default="breakfast,lunch,dinner",
        help="Comma-separated meal types",
    )
    pw.add_argument(
        "--goal",
        default="balanced",
        choices=[g.value for g in GoalType],
    )
    pw.add_argument(
        "--budget",
        default="standard",
        choices=[b.value for b in BudgetClass],
        help="Primary budget class (expanded to compatible allow-list)",
    )
    pw.add_argument("--max-time", type=int, default=45)
    pw.add_argument("--leftovers", action="store_true")
    pw.add_argument("--no-leftovers", action="store_true")
    pw.add_argument(
        "--cook-days",
        default=None,
        help="Comma-separated 1-based cook days (default: all days)",
    )
    pw.add_argument("--exclude-protein", default=None)
    pw.add_argument("--prefer-protein", default=None)
    pw.add_argument("--source-verified-only", action="store_true")
    pw.add_argument("--evaluate", action="store_true")
    pw.add_argument("--db", default=None)
    pw.add_argument("--json", action="store_true")
    pw.add_argument("--beam-width", type=int, default=8)
    pw.add_argument("--pool-size", type=int, default=15)

    dp = sub.add_parser(
        "diagnose-plan",
        help="Planner diagnostics for NO_PLAN / PARTIAL (Sprint 10.11.1)",
    )
    dp.add_argument("--days", type=int, default=7)
    dp.add_argument(
        "--meal-types",
        default="breakfast,lunch,dinner",
        help="Comma-separated meal types",
    )
    dp.add_argument(
        "--goal",
        default="balanced",
        choices=[g.value for g in GoalType],
    )
    dp.add_argument(
        "--budget",
        default="standard",
        choices=[b.value for b in BudgetClass],
    )
    dp.add_argument("--max-time", type=int, default=45)
    dp.add_argument("--leftovers", action="store_true")
    dp.add_argument("--no-leftovers", action="store_true")
    dp.add_argument(
        "--cook-days",
        default=None,
        help="Comma-separated 1-based cook days (default: all days)",
    )
    dp.add_argument("--exclude-protein", default=None)
    dp.add_argument("--prefer-protein", default=None)
    dp.add_argument("--source-verified-only", action="store_true")
    dp.add_argument("--db", default=None)
    dp.add_argument("--json", action="store_true")
    dp.add_argument("--beam-width", type=int, default=8)
    dp.add_argument("--pool-size", type=int, default=15)
    dp.add_argument(
        "--production",
        action="store_true",
        help="Match CatalogMenuGenerationService: allow_cook_day_miss=False",
    )
    dp.add_argument(
        "--from-profile",
        default=None,
        help="Optional JSON profile path; build strategy via StrategyBuilder",
    )

    args = parser.parse_args(argv)

    if args.command == "import":
        importer = RecipeCatalogImporter(
            catalog_root=Path(args.catalog_root) if args.catalog_root else None,
            db_path=args.db,
        )
        report = asyncio.run(importer.import_catalog(mode=args.mode))
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        return 0 if report.ok else 1

    if args.command == "report":
        report = asyncio.run(
            build_catalog_report(db_path=args.db, catalog_root=args.catalog_root)
        )
        if args.json:
            print(report.to_json())
        else:
            log_catalog_report(report)
            print(report.to_json())
        return 0 if not report.validation_errors else 1

    if args.command == "select":
        context = CandidateSelectionContext(
            meal_type=MealType(args.meal_type),
            limit=args.limit,
            goal=GoalType(args.goal) if args.goal else None,
            max_total_time_minutes=args.max_time,
            allowed_budget_classes=_parse_budget_list(args.budget_classes),
            excluded_protein_sources=_parse_proteins(args.exclude_protein),
            preferred_protein_sources=_parse_proteins(args.prefer_protein),
            prefer_batch_friendly=bool(args.batch),
            allow_leftovers=bool(args.leftovers),
            family_mode=bool(args.family),
        )
        selector = RecipeCandidateSelector(db_path=args.db)
        result = asyncio.run(selector.select(context))
        if args.json:
            print(json.dumps(result.to_summary(), ensure_ascii=False, indent=2))
            return 0

        print(
            f"status={result.selection_status.value} "
            f"catalog={result.total_catalog_recipes} "
            f"after_filters={result.after_hard_filters} "
            f"returned={result.returned_count}"
        )
        if result.filter_stats.removed:
            print("filter removals:")
            for code, count in sorted(result.filter_stats.removed.items()):
                print(f"  {code}: {count}")
        for idx, cand in enumerate(result.candidates, start=1):
            print(f"\n{idx}. {cand.recipe.name}")
            print(f"   score: {cand.score:.4f}")
            print("   reasons:")
            for code in cand.reason_codes:
                print(f"   - {code} ({reason_text_ru(code)})")
            print("   breakdown:")
            for key, value in cand.score_breakdown.to_public_dict().items():
                print(f"   {key}: {value:.4f}")
        return 0

    if args.command == "evaluate":
        evaluator = CatalogEvaluator(db_path=args.db)
        report = asyncio.run(
            evaluator.evaluate(
                scenario_file=Path(args.scenario_file) if args.scenario_file else None,
                group=args.group,
            )
        )
        payload = report.model_dump(mode="json")
        text_console = format_console_report(
            report,
            show_critical=args.show_critical,
            show_recommendations=args.show_recommendations,
        )
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.suffix.lower() == ".md":
                out.write_text(format_markdown_report(report), encoding="utf-8")
            else:
                out.write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
        if args.json and not args.output:
            print(json.dumps(payload, ensure_ascii=False, indent=2))
        elif args.json and args.output:
            print(json.dumps(report.to_summary_dict(), ensure_ascii=False, indent=2))
        else:
            print(text_console)
        return 0

    if args.command == "quality-audit":
        auditor = RecipeQualityAuditor(db_path=args.db)
        mode = "apply" if args.apply else "read_only"
        report = asyncio.run(
            auditor.run(mode=mode, recipe_id=args.recipe_id, ensure_provenance=True)
        )
        default_md = (
            Path(__file__).resolve().parents[1] / "recipe_catalog" / "QUALITY_REPORT.md"
        )
        out_path = Path(args.output) if args.output else default_md
        auditor.write_markdown(report, out_path)

        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
            return 0

        print(
            f"quality-audit mode={report.mode} recipes={report.recipe_count} "
            f"passed={report.passed_count} warnings={report.warning_count} "
            f"failed={report.failed_count}"
        )
        print(f"status distribution: {report.status_distribution}")
        print(
            f"source_verified={report.source_verified_count} "
            f"human_reviewed={report.human_reviewed_count} "
            f"kitchen_tested={report.kitchen_tested_count} "
            f"approved={report.approved_count}"
        )
        print(f"report written: {out_path}")

        summary = format_quality_summary(report)
        if args.show_blocking:
            print("\nblocking issues:")
            for r in report.results:
                for e in r.blocking_errors:
                    print(f"  {r.recipe_id}: {e.code} — {e.message}")
            if not any(r.blocking_errors for r in report.results):
                print("  (none)")
        if args.show_recommendations:
            print("\nmetadata recommendations (sample):")
            shown = 0
            for r in report.results:
                for rec in r.recommendations:
                    if rec.reason_code in {
                        "HUMAN_REVIEW_REQUIRED",
                        "SOURCE_VERIFICATION_REQUIRED",
                    }:
                        continue
                    print(
                        f"  {r.recipe_id}: {rec.recommendation_type.value} "
                        f"{rec.field} ({rec.reason_code})"
                    )
                    shown += 1
                    if shown >= 40:
                        break
                if shown >= 40:
                    break
        if args.show_unverified:
            print("\nunverified / no sources:")
            for r in report.results:
                if int(r.source_summary.get("source_count") or 0) == 0:
                    print(f"  {r.recipe_id} creation={r.creation_method}")
        print(f"\ntop warnings: {summary['top_warnings'][:8]}")
        return 0

    if args.command == "source-review":
        return asyncio.run(_cmd_source_review(args))

    if args.command == "source-compare":
        return _cmd_source_compare(args)

    if args.command == "planner-readiness":
        return asyncio.run(_cmd_planner_readiness(args))

    if args.command == "diversity-report":
        return asyncio.run(_cmd_diversity_report(args))

    if args.command == "plan-week":
        return asyncio.run(_cmd_plan_week(args))

    if args.command == "diagnose-plan":
        return asyncio.run(_cmd_diagnose_plan(args))

    return 1


def _load_structured(path: Path) -> object:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        return yaml.safe_load(text)
    return json.loads(text)


def _parse_observations(raw: object) -> list[RecipeSourceObservation]:
    if isinstance(raw, dict) and "observations" in raw:
        raw = raw["observations"]
    if not isinstance(raw, list):
        raise ValueError("observations file must be a list or {observations: [...]}")
    out: list[RecipeSourceObservation] = []
    for item in raw:
        ings = [
            IngredientObservation(**ing) if isinstance(ing, dict) else ing
            for ing in (item.get("ingredients") or [])
        ]
        out.append(
            RecipeSourceObservation(
                source_id=item["source_id"],
                source_type=SourceType(item["source_type"]),
                source_title=item["source_title"],
                source_reference=item["source_reference"],
                publisher_or_author=item.get("publisher_or_author"),
                accessed_at=item.get("accessed_at"),
                ingredients=ings,
                cooking_method=item.get("cooking_method"),
                prep_time_minutes=item.get("prep_time_minutes"),
                cook_time_minutes=item.get("cook_time_minutes"),
                total_time_minutes=item.get("total_time_minutes"),
                temperature_c=item.get("temperature_c"),
                yield_servings=item.get("yield_servings"),
                yield_weight_g=item.get("yield_weight_g"),
                storage_days=item.get("storage_days"),
                notes=item.get("notes"),
                supports_ingredients=bool(item.get("supports_ingredients", True)),
                supports_proportions=bool(item.get("supports_proportions", False)),
                supports_method=bool(item.get("supports_method", False)),
                supports_time=bool(item.get("supports_time", False)),
                supports_yield=bool(item.get("supports_yield", False)),
                supports_storage=bool(item.get("supports_storage", False)),
            )
        )
    return out


async def _cmd_source_review(args: argparse.Namespace) -> int:
    path = Path(args.observations)
    observations = _parse_observations(_load_structured(path))
    repo = RecipeRepository(args.db)
    recipe = await repo.get_recipe_with_dependencies(args.recipe_id)
    if recipe is None:
        print(f"recipe not found: {args.recipe_id}", file=sys.stderr)
        return 1
    reviewer = RecipeSourceReviewer()
    result = reviewer.review(recipe, observations)
    payload = result.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"source-review recipe={result.recipe_id} "
            f"sources={result.source_count} passed={result.passed}"
        )
        if result.notes:
            print("notes:")
            for note in result.notes:
                print(f"  - {note}")
        if result.mismatches:
            print("mismatches:")
            for m in result.mismatches:
                print(f"  - {m.field}: {m.message}")
        else:
            print("mismatches: (none)")
        print(
            "agreement:",
            ", ".join(result.comparison.agreement_fields) or "(none)",
        )
        print(
            "disagreement:",
            ", ".join(result.comparison.disagreement_fields) or "(none)",
        )
    return 0 if result.passed else 2


async def _cmd_planner_readiness(args: argparse.Namespace) -> int:
    out = Path(args.output) if args.output else PLANNER_DEFAULT_PATH
    result = await run_planner_readiness(db_path=args.db, output=out)
    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(
            f"planner-readiness status={result.status} "
            f"recipes={result.total_active_recipes} "
            f"source_verified={result.source_verified}"
        )
        if result.threshold_failures:
            print("failures:")
            for item in result.threshold_failures:
                print(f"  - {item}")
        print(f"report written: {out}")
    return 0


async def _cmd_diversity_report(args: argparse.Namespace) -> int:
    out = Path(args.output) if args.output else DIVERSITY_DEFAULT_PATH
    report = await run_diversity_report(db_path=args.db, output=out)
    if args.json:
        print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    else:
        print(
            f"diversity-report recipes={report.total_active_recipes} "
            f"quick={report.quick_count} slow={report.slow_count} "
            f"vegetarian={report.vegetarian_count}"
        )
        print(f"report written: {out}")
    return 0


def _budget_allow_list(primary: BudgetClass) -> list[BudgetClass]:
    if primary == BudgetClass.VERY_BUDGET:
        return [BudgetClass.VERY_BUDGET, BudgetClass.BUDGET]
    if primary == BudgetClass.BUDGET:
        return [BudgetClass.VERY_BUDGET, BudgetClass.BUDGET]
    if primary == BudgetClass.STANDARD:
        return [BudgetClass.VERY_BUDGET, BudgetClass.BUDGET, BudgetClass.STANDARD]
    return [BudgetClass.BUDGET, BudgetClass.STANDARD, BudgetClass.PREMIUM]


async def _cmd_plan_week(args: argparse.Namespace) -> int:
    from datetime import datetime, timezone

    from recipes.planning.context import build_planning_context_from_strategy
    from recipes.planning.evaluator import WeeklyPlanEvaluator
    from recipes.planning.planner import WeeklyRecipePlanner
    from recipes.planning.weights import WeeklyPlannerConfig
    from recipes.quality.enums import QualityStatus
    from strategy.models import WeeklyStrategy

    meal_types = [
        MealType(part.strip())
        for part in str(args.meal_types).split(",")
        if part.strip()
    ]
    days = int(args.days)
    if args.cook_days:
        cook_days = [int(x.strip()) for x in str(args.cook_days).split(",") if x.strip()]
    else:
        cook_days = list(range(1, days + 1))

    leftovers = True
    if args.no_leftovers:
        leftovers = False
    elif args.leftovers:
        leftovers = True

    strategy_goal = {
        GoalType.BALANCED.value: "healthy",
        GoalType.WEIGHT_LOSS.value: "weightloss",
        GoalType.MUSCLE_GAIN.value: "muscle",
        GoalType.BUDGET.value: "budget",
        GoalType.FAMILY.value: "home",
        GoalType.QUICK_COOKING.value: "healthy",
        GoalType.WEIGHT_MAINTENANCE.value: "healthy",
    }.get(args.goal, "healthy")

    strategy = WeeklyStrategy(
        strategy_version=5,
        goal=strategy_goal,  # type: ignore[arg-type]
        days=days,
        budget=3000.0 if args.budget != "premium" else 10000.0,
        meal_types=[m.value for m in meal_types],  # type: ignore[arg-type]
        meals_per_day=len(meal_types),
        cook_days=cook_days,
        shopping_days=[1],
        leftovers_enabled=leftovers,
        repeat_breakfasts=False,
        repeat_lunches=False,
        repeat_dinners=False,
        preferred_proteins=["any"],
        excluded_products=[],
        cooking_time_limit=int(args.max_time),
        prefer_faster_meals=int(args.max_time) <= 30,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    preferred = _parse_proteins(args.prefer_protein)
    excluded = _parse_proteins(args.exclude_protein)
    config = WeeklyPlannerConfig(
        candidate_pool_size=int(args.pool_size),
        beam_width=int(args.beam_width),
    )
    context = build_planning_context_from_strategy(
        strategy,
        excluded_protein_sources=excluded,
        minimum_quality_status=(
            QualityStatus.SOURCE_VERIFIED if args.source_verified_only else None
        ),
        config=config,
        max_cooking_time_override=int(args.max_time),
        allowed_budget_override=_budget_allow_list(BudgetClass(args.budget)),
        leftovers_override=leftovers,
        goal_override=GoalType(args.goal),
    )
    if preferred:
        context = context.model_copy(update={"preferred_proteins": preferred})

    planner = WeeklyRecipePlanner(repository=RecipeRepository(args.db))
    plan = await planner.plan(context)

    payload: dict = plan.to_summary()
    if args.evaluate:
        recipes = {
            m.recipe_id: r
            for m in plan.meals
            for r in [await planner.repository.get_recipe_with_dependencies(m.recipe_id)]
            if r is not None
        }
        quality = await planner.candidate_provider.load_quality_map()
        evaluation = WeeklyPlanEvaluator().evaluate(
            plan,
            context=context,
            recipes=recipes,
            quality_by_recipe=quality,
        )
        payload["evaluation"] = evaluation.to_dict()

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if plan.status.value == "success" else 2

    print(
        f"plan-week status={plan.status.value} score={plan.score:.3f} "
        f"meals={len(plan.meals)} leftovers="
        f"{sum(1 for m in plan.meals if m.is_leftover)} "
        f"ms={plan.diagnostics.planning_duration_ms:.1f}"
    )
    print(
        f"diagnostics expanded={plan.diagnostics.states_expanded} "
        f"pruned={plan.diagnostics.states_pruned} "
        f"pool={plan.diagnostics.candidate_pool_size} "
        f"beam={plan.diagnostics.beam_width}"
    )
    if plan.diagnostics.unfilled_slots:
        print("unfilled:", ", ".join(plan.diagnostics.unfilled_slots))
        for slot_id, causes in plan.diagnostics.slot_filter_causes.items():
            if slot_id in plan.diagnostics.unfilled_slots:
                print(f"  {slot_id}: {causes}")

    by_day: dict[int, list] = {}
    for meal in plan.meals:
        by_day.setdefault(meal.day_index, []).append(meal)
    for day in sorted(by_day):
        print(f"\nDay {day}:")
        for meal in sorted(by_day[day], key=lambda m: m.meal_type):
            tag = "L" if meal.is_leftover else "C"
            print(
                f"  {meal.meal_type:10} [{tag}] {meal.recipe_name} "
                f"({meal.recipe_id}) score={meal.selection_score:.3f}"
            )

    if args.evaluate and "evaluation" in payload:
        ev = payload["evaluation"]
        print(
            "\nevaluation: "
            f"coverage={ev['slot_coverage']:.2f} "
            f"unique={ev['unique_recipe_ratio']:.2f} "
            f"leftovers={ev['leftover_usage']} "
            f"protein_div={ev['protein_diversity']:.2f}"
        )
    return 0 if plan.status.value == "success" else 2


async def _cmd_diagnose_plan(args: argparse.Namespace) -> int:
    """Sprint 10.11.1 — print planner termination diagnostics."""
    from datetime import datetime, timezone

    from recipes.planning.context import build_planning_context_from_strategy
    from recipes.planning.planner import WeeklyRecipePlanner
    from recipes.planning.weights import WeeklyPlannerConfig
    from recipes.quality.enums import QualityStatus
    from strategy.models import WeeklyStrategy

    from strategy.builder import StrategyBuilder

    goal_to_strategy = {
        GoalType.BALANCED.value: "healthy",
        GoalType.WEIGHT_LOSS.value: "weightloss",
        GoalType.MUSCLE_GAIN.value: "muscle",
        GoalType.BUDGET.value: "budget",
        GoalType.FAMILY.value: "home",
        GoalType.QUICK_COOKING.value: "healthy",
        GoalType.WEIGHT_MAINTENANCE.value: "healthy",
    }
    strategy_goal_to_goaltype = {
        "home": GoalType.FAMILY,
        "budget": GoalType.BUDGET,
        "healthy": GoalType.BALANCED,
        "weightloss": GoalType.WEIGHT_LOSS,
        "muscle": GoalType.MUSCLE_GAIN,
    }

    leftovers = True
    if args.no_leftovers:
        leftovers = False
    elif args.leftovers:
        leftovers = True

    profile_override = None
    if getattr(args, "from_profile", None):
        profile_path = Path(args.from_profile)
        profile_override = json.loads(profile_path.read_text(encoding="utf-8-sig"))
        if not isinstance(profile_override, dict):
            raise SystemExit("--from-profile JSON must be an object")

    if profile_override is not None:
        strategy = StrategyBuilder().build(profile_override)
        meal_types = [MealType(m) for m in strategy.meal_types]
        leftovers = bool(strategy.leftovers_enabled)
        goal_override = strategy_goal_to_goaltype.get(
            str(strategy.goal), GoalType(args.goal)
        )
        max_time = int(strategy.cooking_time_limit or args.max_time)
        budget_override = None
    else:
        meal_types = [
            MealType(part.strip())
            for part in str(args.meal_types).split(",")
            if part.strip()
        ]
        days = int(args.days)
        if args.cook_days:
            cook_days = [
                int(x.strip()) for x in str(args.cook_days).split(",") if x.strip()
            ]
        else:
            cook_days = list(range(1, days + 1))

        strategy_goal = goal_to_strategy.get(args.goal, "healthy")
        strategy = WeeklyStrategy(
            strategy_version=5,
            goal=strategy_goal,  # type: ignore[arg-type]
            days=days,
            budget=3000.0 if args.budget != "premium" else 10000.0,
            meal_types=[m.value for m in meal_types],  # type: ignore[arg-type]
            meals_per_day=len(meal_types),
            cook_days=cook_days,
            shopping_days=[1],
            leftovers_enabled=leftovers,
            repeat_breakfasts=False,
            repeat_lunches=False,
            repeat_dinners=False,
            preferred_proteins=["any"],
            excluded_products=[],
            cooking_time_limit=int(args.max_time),
            prefer_faster_meals=int(args.max_time) <= 30,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        goal_override = GoalType(args.goal)
        max_time = int(args.max_time)
        budget_override = _budget_allow_list(BudgetClass(args.budget))

    preferred = _parse_proteins(args.prefer_protein)
    excluded = _parse_proteins(args.exclude_protein)
    allow_cook_day_miss = not bool(getattr(args, "production", False))
    config = WeeklyPlannerConfig(
        candidate_pool_size=int(args.pool_size),
        beam_width=int(args.beam_width),
        allow_cook_day_miss=allow_cook_day_miss,
    )
    context_kwargs = {
        "excluded_protein_sources": excluded,
        "minimum_quality_status": (
            QualityStatus.SOURCE_VERIFIED if args.source_verified_only else None
        ),
        "config": config,
        "max_cooking_time_override": max_time,
        "leftovers_override": leftovers,
        "goal_override": goal_override,
    }
    if budget_override is not None:
        context_kwargs["allowed_budget_override"] = budget_override

    # Mirror CatalogMenuGenerationService exclusion resolution for --from-profile / allergies.
    exclusion_names: list[str] = list(strategy.excluded_products) + list(
        getattr(strategy, "availability_avoid_products", None) or []
    )
    allergies_raw = ""
    if profile_override is not None:
        allergies_raw = str(profile_override.get("allergies") or "")
    elif getattr(args, "from_profile", None) is None:
        allergies_raw = ""
    if allergies_raw and allergies_raw.strip().lower() not in {"", "нет", "none"}:
        for part in allergies_raw.split(","):
            part = part.strip()
            if part and part.lower() not in {"нет", "none"}:
                exclusion_names.append(part)

    repo = RecipeRepository(args.db)
    if exclusion_names:
        from recipes.selection.ingredient_resolve import resolve_product_names

        ingredients = await repo.list_ingredients()
        resolved = resolve_product_names(exclusion_names, ingredients)
        context_kwargs["excluded_ingredient_ids"] = set(resolved.resolved_ids)

    # Also mirror allergy→excluded protein tags when profile allergies present.
    if allergies_raw and allergies_raw.strip().lower() not in {"", "нет", "none"}:
        try:
            from menu_generation.catalog_service import _parse_excluded_proteins

            allergy_proteins = _parse_excluded_proteins(allergies_raw)
            if allergy_proteins:
                merged = set(context_kwargs.get("excluded_protein_sources") or set())
                merged |= set(allergy_proteins)
                context_kwargs["excluded_protein_sources"] = merged
        except Exception:
            pass

    context = build_planning_context_from_strategy(strategy, **context_kwargs)
    if preferred:
        context = context.model_copy(update={"preferred_proteins": preferred})

    planner = WeeklyRecipePlanner(repository=repo)
    plan = await planner.plan(context)
    diag = plan.diagnostics

    if args.json:
        print(
            json.dumps(
                {
                    "status": plan.status.value,
                    "score": plan.score,
                    "diagnostics": diag.to_dict(),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if plan.status.value == "success" else 2

    print(
        f"diagnose-plan status={plan.status.value} "
        f"termination={diag.termination_reason}"
    )
    print(
        f"failed_slot={diag.failed_slot} "
        f"last_successful={diag.last_successful_slot}"
    )
    print(
        f"slots={diag.slots_completed}/{diag.slots_total} "
        f"visited={diag.visited_states} "
        f"expanded={diag.expanded_states} "
        f"iterations={diag.beam_iterations} "
        f"ms={diag.planning_duration_ms:.1f}"
    )
    if diag.hard_filter_stats:
        print("hard_filter_stats:", diag.hard_filter_stats)
    if diag.constraint_statistics:
        print("constraint_statistics:", diag.constraint_statistics)
    if diag.beam_metrics:
        print("beam_metrics:", diag.beam_metrics)
    if diag.partial_plan:
        print(
            "partial_plan assignments:",
            len(diag.partial_plan.get("assignments") or []),
        )
        for item in (diag.partial_plan.get("assignments") or [])[:10]:
            print(
                f"  {item.get('slot_id')}: {item.get('recipe_id')} "
                f"leftover={item.get('is_leftover')}"
            )
    if diag.slots:
        print("\nslot table:")
        print(
            f"{'slot':22} {'meal':10} {'fill':5} "
            f"{'before':6} {'hard':5} {'weekly':6} selected/fail"
        )
        for s in diag.slots:
            print(
                f"{s.slot_id:22} {s.meal_type:10} "
                f"{'yes' if s.filled else 'no':5} "
                f"{s.candidate_count_before_filters:6} "
                f"{s.candidate_count_after_hard_filters:5} "
                f"{s.candidate_count_after_weekly_constraints:6} "
                f"{s.selected_recipe_id or s.failure_reason or '-'}"
            )
    if diag.best_failed_candidates:
        print("\nbest_failed_candidates:")
        for c in diag.best_failed_candidates:
            print(
                f"  {c.recipe_id} score={c.selector_score:.3f} "
                f"reason={c.reject_reason} {c.detail}"
            )
    return 0 if plan.status.value == "success" else 2


def _cmd_source_compare(args: argparse.Namespace) -> int:
    concept_raw = _load_structured(Path(args.concept))
    if not isinstance(concept_raw, dict):
        print("concept file must be an object", file=sys.stderr)
        return 1
    concept = RecipeConcept(**concept_raw)
    observations = _parse_observations(_load_structured(Path(args.observations)))
    draft = SourceBackedDraftBuilder().build(concept, observations)
    payload = draft.to_dict()
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(
            f"source-compare concept={concept.concept_id} "
            f"ready={draft.ready_for_catalog_import} "
            f"confidence={draft.confidence:.2f}"
        )
        if draft.blocking_reasons:
            print("blocking:")
            for reason in draft.blocking_reasons:
                print(f"  - {reason}")
        print("ingredients:", ", ".join(i.name for i in draft.normalized_ingredients))
        print("method:", draft.normalized_method)
        print("total_time:", draft.normalized_total_time_minutes)
    return 0 if draft.ready_for_catalog_import else 2


if __name__ == "__main__":
    sys.exit(main())
