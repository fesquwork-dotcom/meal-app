"""CLI: python -m recipes.cli import|report|select"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys

from recipes.catalog_report import build_catalog_report, log_catalog_report
from recipes.enums import BudgetClass, GoalType, MealType, ProteinSourceTag
from recipes.importer import RecipeCatalogImporter
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
    sel.add_argument(
        "--budget-classes",
        default=None,
        help="Comma-separated: very_budget,budget,standard,premium",
    )
    sel.add_argument(
        "--exclude-protein",
        default=None,
        help="Comma-separated protein_source tags to exclude",
    )
    sel.add_argument(
        "--prefer-protein",
        default=None,
        help="Comma-separated preferred protein_source tags",
    )
    sel.add_argument("--batch", action="store_true")
    sel.add_argument("--leftovers", action="store_true")
    sel.add_argument("--family", action="store_true")
    sel.add_argument("--db", default=None)
    sel.add_argument("--json", action="store_true")

    args = parser.parse_args(argv)

    if args.command == "import":
        importer = RecipeCatalogImporter(
            catalog_root=args.catalog_root,
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

    return 1


if __name__ == "__main__":
    sys.exit(main())
