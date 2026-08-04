"""CLI: python -m recipes.cli import|report|select|evaluate|quality-audit"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from recipes.catalog_report import build_catalog_report, log_catalog_report
from recipes.enums import BudgetClass, GoalType, MealType, ProteinSourceTag
from recipes.evaluation.engine import CatalogEvaluator
from recipes.evaluation.report_format import format_console_report, format_markdown_report
from recipes.importer import RecipeCatalogImporter
from recipes.quality.audit import RecipeQualityAuditor
from recipes.quality.report import format_quality_summary
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

    return 1


if __name__ == "__main__":
    sys.exit(main())
