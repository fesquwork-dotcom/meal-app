"""Catalog diversity report (Sprint 10.9)."""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from recipes.enums import (
    DietaryTag,
    MealType,
    ProteinSourceTag,
    TagType,
)
from recipes.importer import DEFAULT_CATALOG_ROOT
from recipes.models import Recipe
from recipes.planner_readiness import PlannerReadinessAnalyzer
from recipes.repository import RecipeRepository

DEFAULT_REPORT_PATH = DEFAULT_CATALOG_ROOT / "DIVERSITY_REPORT.md"
QUICK_TIME_MAX = 30
TOP_INGREDIENTS = 25

# Heuristic floors for "underrepresented" callouts relative to active catalog size
UNDERREP_PROTEIN_MAX_SHARE = 0.08
UNDERREP_CUISINE_MAX = 2
UNDERREP_METHOD_MAX = 2


@dataclass
class DiversityReport:
    total_active_recipes: int = 0
    by_protein_source: dict[str, int] = field(default_factory=dict)
    by_meal_type_primary: dict[str, int] = field(default_factory=dict)
    by_meal_type_membership: dict[str, int] = field(default_factory=dict)
    by_cooking_method: dict[str, int] = field(default_factory=dict)
    by_cuisine: dict[str, int] = field(default_factory=dict)
    by_budget_class: dict[str, int] = field(default_factory=dict)
    quick_count: int = 0
    slow_count: int = 0
    vegetarian_count: int = 0
    ingredient_recipe_counts: dict[str, int] = field(default_factory=dict)
    top_ingredients: list[tuple[str, int, str]] = field(default_factory=list)
    single_use_ingredients: list[tuple[str, str]] = field(default_factory=list)
    dominant_ingredients: list[tuple[str, int, str]] = field(default_factory=list)
    underrepresented: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DiversityReporter:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.repository = RecipeRepository(db_path)
        self._loader = PlannerReadinessAnalyzer(db_path=db_path)

    async def build(self) -> DiversityReport:
        recipes = await self._loader._load_active_recipes()
        report = DiversityReport(total_active_recipes=len(recipes))
        if not recipes:
            return report

        report.by_protein_source = _count_tags(recipes, TagType.PROTEIN_SOURCE)
        report.by_meal_type_primary = dict(
            sorted(Counter(r.primary_meal_type.value for r in recipes).items())
        )
        membership: Counter[str] = Counter()
        for recipe in recipes:
            meal_set = {m.meal_type.value for m in recipe.meal_types}
            meal_set.add(recipe.primary_meal_type.value)
            for mt in meal_set:
                membership[mt] += 1
        report.by_meal_type_membership = dict(sorted(membership.items()))

        method_counter: Counter[str] = Counter()
        for recipe in recipes:
            if recipe.cooking_methods:
                for method in recipe.cooking_methods:
                    method_counter[method.value] += 1
            else:
                method_counter["(none)"] += 1
        report.by_cooking_method = dict(sorted(method_counter.items()))

        report.by_cuisine = _count_tags(recipes, TagType.CUISINE)
        report.by_budget_class = dict(
            sorted(Counter(r.budget_class.value for r in recipes).items())
        )

        report.quick_count = sum(
            1 for r in recipes if r.total_time_minutes <= QUICK_TIME_MAX
        )
        report.slow_count = sum(
            1 for r in recipes if r.total_time_minutes > QUICK_TIME_MAX
        )
        report.vegetarian_count = sum(1 for r in recipes if _is_vegetarian(r))

        # Ingredient reuse
        recipe_counts: Counter[str] = Counter()
        display_names: dict[str, str] = {}
        for recipe in recipes:
            seen: set[str] = set()
            for ri in recipe.ingredients:
                iid = ri.ingredient_id
                if iid in seen:
                    continue
                seen.add(iid)
                recipe_counts[iid] += 1
                if ri.ingredient is not None:
                    display_names[iid] = ri.ingredient.display_name
                else:
                    display_names.setdefault(iid, iid)

        report.ingredient_recipe_counts = dict(recipe_counts)
        ranked = sorted(recipe_counts.items(), key=lambda x: (-x[1], x[0]))
        report.top_ingredients = [
            (iid, count, display_names.get(iid, iid))
            for iid, count in ranked[:TOP_INGREDIENTS]
        ]
        report.single_use_ingredients = [
            (iid, display_names.get(iid, iid))
            for iid, count in ranked
            if count == 1
        ]
        # Dominant: appear in >= 20% of recipes (or top 5 if catalog tiny)
        threshold = max(2, int(len(recipes) * 0.2))
        report.dominant_ingredients = [
            (iid, count, display_names.get(iid, iid))
            for iid, count in ranked
            if count >= threshold
        ][:15]

        report.underrepresented = _underrepresented(report, len(recipes))
        return report


def _count_tags(recipes: list[Recipe], tag_type: TagType) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for recipe in recipes:
        values = [t.tag_value for t in recipe.tags if t.tag_type == tag_type]
        if values:
            for v in values:
                counter[v] += 1
        else:
            counter["(untagged)"] += 1
    return dict(sorted(counter.items()))


def _is_vegetarian(recipe: Recipe) -> bool:
    if any(
        t.tag_type == TagType.DIETARY and t.tag_value == DietaryTag.VEGETARIAN.value
        for t in recipe.tags
    ):
        return True
    return any(
        t.tag_type == TagType.PROTEIN_SOURCE
        and t.tag_value == ProteinSourceTag.LEGUMES.value
        for t in recipe.tags
    )


def _underrepresented(report: DiversityReport, n: int) -> list[str]:
    notes: list[str] = []
    if n <= 0:
        return notes

    for protein, count in report.by_protein_source.items():
        if protein == "(untagged)":
            continue
        if count / n <= UNDERREP_PROTEIN_MAX_SHARE:
            notes.append(f"protein `{protein}` only {count}/{n}")

    expected_proteins = {p.value for p in ProteinSourceTag} - {
        ProteinSourceTag.NONE.value,
        ProteinSourceTag.MIXED.value,
    }
    present = set(report.by_protein_source) - {"(untagged)"}
    for missing in sorted(expected_proteins - present):
        notes.append(f"protein `{missing}` absent")

    for cuisine, count in report.by_cuisine.items():
        if cuisine != "(untagged)" and count <= UNDERREP_CUISINE_MAX:
            notes.append(f"cuisine `{cuisine}` only {count}")

    for method, count in report.by_cooking_method.items():
        if method != "(none)" and count <= UNDERREP_METHOD_MAX:
            notes.append(f"cooking_method `{method}` only {count}")

    for meal in (MealType.BREAKFAST.value, MealType.LUNCH.value, MealType.DINNER.value):
        membership = report.by_meal_type_membership.get(meal, 0)
        if membership < max(5, n // 5):
            notes.append(f"meal_type `{meal}` membership only {membership}")

    if report.vegetarian_count < max(3, n // 10):
        notes.append(f"vegetarian only {report.vegetarian_count}/{n}")

    if report.quick_count < max(5, n // 5):
        notes.append(f"quick (≤{QUICK_TIME_MAX}m) only {report.quick_count}/{n}")

    return notes


def format_diversity_markdown(report: DiversityReport) -> str:
    lines: list[str] = [
        "# Recipe Catalog Diversity Report",
        "",
        f"**Active recipes:** {report.total_active_recipes}",
        "",
        "## Protein source distribution",
        "",
    ]
    _append_counts(lines, report.by_protein_source)

    lines.extend(["", "## Meal type distribution", "", "### Primary", ""])
    _append_counts(lines, report.by_meal_type_primary)
    lines.extend(["", "### Membership (multi-meal counted)", ""])
    _append_counts(lines, report.by_meal_type_membership)

    lines.extend(["", "## Cooking method distribution", ""])
    _append_counts(lines, report.by_cooking_method)

    lines.extend(["", "## Cuisine distribution", ""])
    _append_counts(lines, report.by_cuisine)

    lines.extend(["", "## Budget distribution", ""])
    _append_counts(lines, report.by_budget_class)

    lines.extend(
        [
            "",
            "## Quick / slow",
            "",
            f"- Quick (total ≤ {QUICK_TIME_MAX} min): **{report.quick_count}**",
            f"- Slow (total > {QUICK_TIME_MAX} min): **{report.slow_count}**",
            "",
            "## Vegetarian",
            "",
            f"- Count: **{report.vegetarian_count}** "
            "(dietary `vegetarian` or protein `legumes`)",
            "",
            "## Ingredient reuse",
            "",
            f"### Top {TOP_INGREDIENTS} ingredients by recipe_count",
            "",
        ]
    )
    if report.top_ingredients:
        for iid, count, name in report.top_ingredients:
            lines.append(f"- `{iid}` ({name}): {count}")
    else:
        lines.append("- (none)")

    lines.extend(
        [
            "",
            f"### Single-use ingredients ({len(report.single_use_ingredients)})",
            "",
        ]
    )
    if report.single_use_ingredients:
        for iid, name in report.single_use_ingredients[:40]:
            lines.append(f"- `{iid}` ({name})")
        if len(report.single_use_ingredients) > 40:
            lines.append(
                f"- … and {len(report.single_use_ingredients) - 40} more"
            )
    else:
        lines.append("- (none)")

    lines.extend(["", "## Dominant ingredients", ""])
    if report.dominant_ingredients:
        for iid, count, name in report.dominant_ingredients:
            lines.append(f"- `{iid}` ({name}): {count}")
    else:
        lines.append("- (none above threshold)")

    lines.extend(["", "## Underrepresented categories", ""])
    if report.underrepresented:
        for note in report.underrepresented:
            lines.append(f"- {note}")
    else:
        lines.append("- (none flagged)")
    lines.append("")
    return "\n".join(lines)


def _append_counts(lines: list[str], counts: dict[str, int]) -> None:
    if not counts:
        lines.append("- (none)")
        return
    for key, value in counts.items():
        lines.append(f"- `{key}`: {value}")


async def run_diversity_report(
    db_path: Path | str | None = None,
    output: Path | str | None = None,
) -> DiversityReport:
    reporter = DiversityReporter(db_path=db_path)
    report = await reporter.build()
    out = Path(output) if output else DEFAULT_REPORT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(format_diversity_markdown(report), encoding="utf-8")
    return report
