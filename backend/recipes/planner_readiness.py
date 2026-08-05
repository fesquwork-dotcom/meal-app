"""Weekly Planner readiness analyzer (Sprint 10.9).

Rule-based metrics over the active recipe catalog — does not create recipes.
"""

from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from recipes.enums import (
    BudgetClass,
    DietaryTag,
    MealType,
    ProteinLevel,
    ProteinSourceTag,
    RecipeRole,
    TagType,
    UsageTag,
)
from recipes.importer import DEFAULT_CATALOG_ROOT
from recipes.models import Recipe
from recipes.quality.enums import QualityStatus
from recipes.repository import RecipeRepository

GOAL_SCORE_MIN = 0.6
QUICK_TIME_MAX = 30
HIGH_PROTEIN_G_PER_100G = 10.0
MIN_RECIPES_FOR_V1 = 60

POULTRY_PROTEINS = frozenset(
    {ProteinSourceTag.CHICKEN.value, ProteinSourceTag.TURKEY.value}
)

# UsageTag has no portable value — portable is role-only unless enum gains one.
_PORTABLE_USAGE: str | None = (
    "portable" if "portable" in {t.value for t in UsageTag} else None
)

DEFAULT_REPORT_PATH = DEFAULT_CATALOG_ROOT / "PLANNER_READINESS_REPORT.md"


@dataclass
class MealTypeReadinessSlice:
    meal_type: str
    membership_count: int = 0
    quick: int = 0
    budget_or_very_budget: int = 0
    high_protein: int = 0
    non_poultry: int = 0
    batch_or_leftover: int = 0
    vegetarian: int = 0
    thresholds_met: dict[str, bool] = field(default_factory=dict)


@dataclass
class PlannerReadinessResult:
    status: str = "not_ready"
    total_active_recipes: int = 0
    by_primary_meal_type: dict[str, int] = field(default_factory=dict)
    by_meal_type_membership: dict[str, int] = field(default_factory=dict)
    by_protein_source: dict[str, int] = field(default_factory=dict)
    by_budget_class: dict[str, int] = field(default_factory=dict)
    by_goal: dict[str, int] = field(default_factory=dict)
    quick: int = 0
    batch: int = 0
    leftover: int = 0
    portable: int = 0
    family: int = 0
    source_verified: int = 0
    relations_count: int = 0
    recipes_without_relations: int = 0
    protein_diversity: float = 0.0
    budget_diversity: float = 0.0
    time_diversity: float = 0.0
    meal_slices: dict[str, MealTypeReadinessSlice] = field(default_factory=dict)
    threshold_failures: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return payload

    def to_metrics_dict(self) -> dict[str, Any]:
        """Compact metrics suitable for baseline snapshots."""
        return {
            "status": self.status,
            "recipes": self.total_active_recipes,
            "by_primary_meal_type": dict(self.by_primary_meal_type),
            "by_meal_type_membership": dict(self.by_meal_type_membership),
            "by_protein_source": dict(self.by_protein_source),
            "by_budget_class": dict(self.by_budget_class),
            "by_goal": dict(self.by_goal),
            "quick": self.quick,
            "batch": self.batch,
            "leftover": self.leftover,
            "portable": self.portable,
            "family": self.family,
            "source_verified": self.source_verified,
            "relations_count": self.relations_count,
            "recipes_without_relations": self.recipes_without_relations,
            "protein_diversity": self.protein_diversity,
            "budget_diversity": self.budget_diversity,
            "time_diversity": self.time_diversity,
            "meal_slices": {
                k: asdict(v) for k, v in self.meal_slices.items()
            },
            "threshold_failures": list(self.threshold_failures),
        }


class PlannerReadinessAnalyzer:
    def __init__(self, db_path: Path | str | None = None) -> None:
        self.repository = RecipeRepository(db_path)
        self.db_path = self.repository.db_path

    async def _load_active_recipes(self) -> list[Recipe]:
        """Same bulk path the selector / evaluator uses."""
        by_id: dict[str, Recipe] = {}
        for meal in (
            MealType.BREAKFAST,
            MealType.LUNCH,
            MealType.DINNER,
            MealType.SNACK,
        ):
            rows = await self.repository.find_candidate_recipes_with_deps(
                meal_type=meal
            )
            for recipe in rows:
                by_id[recipe.id] = recipe
        active = await self.repository.list_active()
        for stub in active:
            if stub.id not in by_id:
                full = await self.repository.get_recipe_with_dependencies(stub.id)
                if full is not None:
                    by_id[full.id] = full
        return sorted(by_id.values(), key=lambda r: r.id)

    async def _source_verified_ids(self, recipe_ids: list[str]) -> set[str]:
        if not recipe_ids:
            return set()
        verified_statuses = {
            QualityStatus.SOURCE_VERIFIED.value,
        }
        verified: set[str] = set()
        async with self.repository._connection() as db:
            placeholders = ",".join("?" for _ in recipe_ids)
            cur = await db.execute(
                f"""
                SELECT recipe_id, quality_status FROM recipe_provenance
                WHERE recipe_id IN ({placeholders})
                """,
                recipe_ids,
            )
            for row in await cur.fetchall():
                if row["quality_status"] in verified_statuses:
                    verified.add(row["recipe_id"])
        return verified

    async def analyze(self) -> PlannerReadinessResult:
        recipes = await self._load_active_recipes()
        relations = await self.repository.get_relations()
        related_ids: set[str] = set()
        for rel in relations:
            related_ids.add(rel.source_recipe_id)
            related_ids.add(rel.target_recipe_id)

        result = PlannerReadinessResult(total_active_recipes=len(recipes))
        if not recipes:
            result.status = "not_ready"
            result.threshold_failures.append("no_active_recipes")
            result.metrics = result.to_metrics_dict()
            return result

        primary = Counter(r.primary_meal_type.value for r in recipes)
        result.by_primary_meal_type = dict(sorted(primary.items()))

        membership: Counter[str] = Counter()
        for recipe in recipes:
            meal_set = {m.meal_type.value for m in recipe.meal_types}
            meal_set.add(recipe.primary_meal_type.value)
            for mt in meal_set:
                membership[mt] += 1
        result.by_meal_type_membership = dict(sorted(membership.items()))

        protein_counter: Counter[str] = Counter()
        for recipe in recipes:
            tags = [
                t.tag_value
                for t in recipe.tags
                if t.tag_type == TagType.PROTEIN_SOURCE
            ]
            if tags:
                for tag in tags:
                    protein_counter[tag] += 1
            else:
                protein_counter["(untagged)"] += 1
        result.by_protein_source = dict(sorted(protein_counter.items()))

        budget = Counter(r.budget_class.value for r in recipes)
        result.by_budget_class = dict(sorted(budget.items()))

        goal_counter: Counter[str] = Counter()
        for recipe in recipes:
            for g in recipe.goal_scores:
                if g.score >= GOAL_SCORE_MIN:
                    goal_counter[g.goal.value] += 1
        result.by_goal = dict(sorted(goal_counter.items()))

        result.quick = sum(1 for r in recipes if _is_quick(r))
        result.batch = sum(1 for r in recipes if r.batch_friendly)
        result.leftover = sum(1 for r in recipes if r.leftover_friendly)
        result.portable = sum(1 for r in recipes if _is_portable(r))
        result.family = sum(
            1
            for r in recipes
            if any(role.role == RecipeRole.FAMILY_MEAL for role in r.roles)
        )

        verified = await self._source_verified_ids([r.id for r in recipes])
        result.source_verified = len(verified)

        result.relations_count = len(relations)
        result.recipes_without_relations = sum(
            1 for r in recipes if r.id not in related_ids
        )

        result.protein_diversity = _diversity_index(protein_counter)
        result.budget_diversity = _diversity_index(budget)
        time_buckets = Counter(_time_bucket(r.total_time_minutes) for r in recipes)
        result.time_diversity = _diversity_index(time_buckets)

        recipes_by_meal: dict[str, list[Recipe]] = defaultdict(list)
        for recipe in recipes:
            meal_set = {m.meal_type.value for m in recipe.meal_types}
            meal_set.add(recipe.primary_meal_type.value)
            for mt in meal_set:
                recipes_by_meal[mt].append(recipe)

        for mt in (MealType.BREAKFAST.value, MealType.LUNCH.value, MealType.DINNER.value):
            slice_recipes = recipes_by_meal.get(mt, [])
            result.meal_slices[mt] = _build_meal_slice(mt, slice_recipes)

        result.status, result.threshold_failures = _evaluate_status(result)
        result.metrics = result.to_metrics_dict()
        return result


def _is_quick(recipe: Recipe) -> bool:
    if recipe.total_time_minutes <= QUICK_TIME_MAX:
        return True
    return any(role.role == RecipeRole.QUICK_MEAL for role in recipe.roles)


def _is_portable(recipe: Recipe) -> bool:
    if any(role.role == RecipeRole.PORTABLE_MEAL for role in recipe.roles):
        return True
    if _PORTABLE_USAGE is None:
        return False
    return any(
        t.tag_type == TagType.USAGE and t.tag_value == _PORTABLE_USAGE
        for t in recipe.tags
    )


def _is_high_protein(recipe: Recipe) -> bool:
    if recipe.protein_level == ProteinLevel.HIGH:
        return True
    return recipe.protein_g_per_100g >= HIGH_PROTEIN_G_PER_100G


def _protein_tags(recipe: Recipe) -> set[str]:
    return {
        t.tag_value
        for t in recipe.tags
        if t.tag_type == TagType.PROTEIN_SOURCE
    }


def _is_non_poultry(recipe: Recipe) -> bool:
    tags = _protein_tags(recipe)
    if not tags:
        return False
    return not (tags & POULTRY_PROTEINS)


def _is_vegetarian(recipe: Recipe) -> bool:
    if any(
        t.tag_type == TagType.DIETARY and t.tag_value == DietaryTag.VEGETARIAN.value
        for t in recipe.tags
    ):
        return True
    return ProteinSourceTag.LEGUMES.value in _protein_tags(recipe)


def _is_budgetish(recipe: Recipe) -> bool:
    return recipe.budget_class in {BudgetClass.VERY_BUDGET, BudgetClass.BUDGET}


def _time_bucket(minutes: int) -> str:
    if minutes <= 15:
        return "0-15"
    if minutes <= 30:
        return "16-30"
    if minutes <= 45:
        return "31-45"
    if minutes <= 60:
        return "46-60"
    return "60+"


def _diversity_index(counts: Counter[str] | dict[str, int]) -> float:
    """Normalized Shannon diversity in [0, 1]. 0 if empty / single class."""
    total = sum(counts.values())
    if total <= 0:
        return 0.0
    n = len(counts)
    if n <= 1:
        return 0.0

    entropy = 0.0
    for c in counts.values():
        if c <= 0:
            continue
        p = c / total
        entropy -= p * math.log(p)
    return round(entropy / math.log(n), 4)


def _build_meal_slice(meal_type: str, recipes: list[Recipe]) -> MealTypeReadinessSlice:
    slice_ = MealTypeReadinessSlice(
        meal_type=meal_type,
        membership_count=len(recipes),
        quick=sum(1 for r in recipes if _is_quick(r)),
        budget_or_very_budget=sum(1 for r in recipes if _is_budgetish(r)),
        high_protein=sum(1 for r in recipes if _is_high_protein(r)),
        non_poultry=sum(1 for r in recipes if _is_non_poultry(r)),
        batch_or_leftover=sum(
            1 for r in recipes if r.batch_friendly or r.leftover_friendly
        ),
        vegetarian=sum(1 for r in recipes if _is_vegetarian(r)),
    )
    met: dict[str, bool] = {
        "quick_ge_5": slice_.quick >= 5,
        "budget_ge_5": slice_.budget_or_very_budget >= 5,
        "high_protein_ge_5": slice_.high_protein >= 5,
    }
    if meal_type in {MealType.LUNCH.value, MealType.DINNER.value}:
        met["non_poultry_ge_4"] = slice_.non_poultry >= 4
        met["batch_or_leftover_ge_4"] = slice_.batch_or_leftover >= 4
        met["vegetarian_ge_3"] = slice_.vegetarian >= 3
    # Breakfast: no non-poultry / batch / vegetarian floor (eggs/dairy OK)
    slice_.thresholds_met = met
    return slice_


def _evaluate_status(
    result: PlannerReadinessResult,
) -> tuple[str, list[str]]:
    failures: list[str] = []
    if result.total_active_recipes < MIN_RECIPES_FOR_V1:
        failures.append(
            f"recipes_{result.total_active_recipes}_lt_{MIN_RECIPES_FOR_V1}"
        )
        return "not_ready", failures

    membership = result.by_meal_type_membership
    checks = [
        ("breakfast_membership_ge_20", membership.get("breakfast", 0) >= 20),
        ("lunch_membership_ge_25", membership.get("lunch", 0) >= 25),
        ("dinner_membership_ge_25", membership.get("dinner", 0) >= 25),
        ("source_verified_ge_50", result.source_verified >= 50),
    ]
    for name, ok in checks:
        if not ok:
            failures.append(name)

    for mt in (MealType.BREAKFAST.value, MealType.LUNCH.value, MealType.DINNER.value):
        slice_ = result.meal_slices.get(mt)
        if slice_ is None:
            failures.append(f"{mt}_slice_missing")
            continue
        for key, ok in slice_.thresholds_met.items():
            if not ok:
                failures.append(f"{mt}_{key}")

    if not failures:
        return "ready_for_v1", failures
    return "limited", failures


def format_planner_readiness_markdown(result: PlannerReadinessResult) -> str:
    lines: list[str] = [
        "# Weekly Planner Readiness Report",
        "",
        f"**Status:** `{result.status}`",
        f"**Active recipes:** {result.total_active_recipes}",
        f"**Source verified:** {result.source_verified}",
        "",
        "## Counts",
        "",
        f"- Quick: **{result.quick}**",
        f"- Batch-friendly: **{result.batch}**",
        f"- Leftover-friendly: **{result.leftover}**",
        f"- Portable: **{result.portable}**",
        f"- Family: **{result.family}**",
        f"- Relations: **{result.relations_count}** "
        f"(recipes without: **{result.recipes_without_relations}**)",
        "",
        "## Diversity (normalized Shannon)",
        "",
        f"- Protein: **{result.protein_diversity}**",
        f"- Budget: **{result.budget_diversity}**",
        f"- Time: **{result.time_diversity}**",
        "",
        "## By primary meal type",
        "",
    ]
    for k, v in result.by_primary_meal_type.items():
        lines.append(f"- `{k}`: {v}")
    lines.extend(["", "## By meal type membership", ""])
    for k, v in result.by_meal_type_membership.items():
        lines.append(f"- `{k}`: {v}")
    lines.extend(["", "## By protein source", ""])
    for k, v in result.by_protein_source.items():
        lines.append(f"- `{k}`: {v}")
    lines.extend(["", "## By budget class", ""])
    for k, v in result.by_budget_class.items():
        lines.append(f"- `{k}`: {v}")
    lines.extend(["", f"## By goal (score ≥ {GOAL_SCORE_MIN})", ""])
    if result.by_goal:
        for k, v in result.by_goal.items():
            lines.append(f"- `{k}`: {v}")
    else:
        lines.append("- (none)")
    lines.extend(["", "## Per-meal readiness slices", ""])
    for mt in ("breakfast", "lunch", "dinner"):
        slice_ = result.meal_slices.get(mt)
        if slice_ is None:
            continue
        lines.append(f"### {mt}")
        lines.append("")
        lines.append(f"- membership: {slice_.membership_count}")
        lines.append(f"- quick: {slice_.quick}")
        lines.append(f"- budget/very_budget: {slice_.budget_or_very_budget}")
        lines.append(f"- high_protein: {slice_.high_protein}")
        lines.append(f"- non_poultry: {slice_.non_poultry}")
        lines.append(f"- batch_or_leftover: {slice_.batch_or_leftover}")
        lines.append(f"- vegetarian: {slice_.vegetarian}")
        unmet = [k for k, ok in slice_.thresholds_met.items() if not ok]
        if unmet:
            lines.append(f"- unmet: {', '.join(f'`{u}`' for u in unmet)}")
        else:
            lines.append("- unmet: (none)")
        lines.append("")
    lines.extend(["## Threshold failures", ""])
    if result.threshold_failures:
        for f in result.threshold_failures:
            lines.append(f"- `{f}`")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.extend(
        [
            "## Ready-for-v1 rules",
            "",
            f"- Active recipes ≥ {MIN_RECIPES_FOR_V1}",
            "- Breakfast membership ≥ 20, lunch ≥ 25, dinner ≥ 25",
            "- Source verified ≥ 50",
            "- Per breakfast/lunch/dinner: ≥5 quick, ≥5 budget/very_budget, ≥5 high protein",
            "- Lunch/dinner: ≥4 non-poultry, ≥4 batch|leftover, ≥3 vegetarian",
            "",
        ]
    )
    return "\n".join(lines)


async def run_planner_readiness(
    db_path: Path | str | None = None,
    output: Path | str | None = None,
) -> PlannerReadinessResult:
    analyzer = PlannerReadinessAnalyzer(db_path=db_path)
    result = await analyzer.analyze()
    out = Path(output) if output else DEFAULT_REPORT_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(format_planner_readiness_markdown(result), encoding="utf-8")
    return result


async def write_baseline_snapshot(
    path: Path | str,
    *,
    db_path: Path | str | None = None,
) -> dict[str, Any]:
    """Analyze current catalog and write metrics JSON to ``path``."""
    analyzer = PlannerReadinessAnalyzer(db_path=db_path)
    result = await analyzer.analyze()
    payload = result.to_metrics_dict()
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return payload
