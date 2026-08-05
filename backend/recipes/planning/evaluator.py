"""Post-hoc weekly plan evaluation metrics (does not change Selector)."""

from __future__ import annotations

from collections import Counter
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from recipes.enums import MealType
from recipes.models import Recipe
from recipes.planning.candidate_provider import primary_protein, recipe_ingredient_ids
from recipes.planning.context import WeeklyPlanningContext
from recipes.planning.models import WeeklyRecipePlan
from recipes.planning.slots import build_weekly_slots


class WeeklyPlanEvaluation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_coverage: float = 0.0
    unique_recipe_ratio: float = 0.0
    exact_repeat_count: int = 0
    protein_diversity: float = 0.0
    consecutive_protein_repeats: int = 0
    quick_meal_count: int = 0
    batch_usage: int = 0
    leftover_usage: int = 0
    cooking_events: int = 0
    cook_day_alignment: float = 0.0
    ingredient_reuse: float = 0.0
    source_verified_ratio: float | None = None
    average_selector_score: float = 0.0
    weekly_score: float = 0.0
    extras: dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class WeeklyPlanEvaluator:
    def evaluate(
        self,
        plan: WeeklyRecipePlan,
        *,
        context: WeeklyPlanningContext,
        recipes: dict[str, Recipe] | None = None,
        quality_by_recipe: dict[str, str] | None = None,
    ) -> WeeklyPlanEvaluation:
        slots = build_weekly_slots(context)
        required = [s for s in slots if s.requires_recipe]
        coverage = len(plan.meals) / max(1, len(required))

        cooks = [m for m in plan.meals if not m.is_leftover]
        cook_ids = [m.recipe_id for m in cooks]
        unique_ratio = len(set(cook_ids)) / max(1, len(cook_ids))
        counts = Counter(cook_ids)
        exact_repeats = sum(max(0, c - 1) for c in counts.values())

        proteins: list[str] = []
        for m in cooks:
            recipe = (recipes or {}).get(m.recipe_id)
            if recipe is None:
                continue
            if m.meal_type == MealType.BREAKFAST.value:
                continue
            p = primary_protein(recipe)
            if p:
                proteins.append(p)
        protein_div = len(set(proteins)) / max(1, len(proteins)) if proteins else 1.0

        consec = 0
        ordered = sorted(plan.meals, key=lambda m: (m.day_index, m.meal_type))
        for i in range(1, len(ordered)):
            a, b = ordered[i - 1], ordered[i]
            if a.meal_type == "breakfast" or b.meal_type == "breakfast":
                continue
            ra = (recipes or {}).get(a.recipe_id)
            rb = (recipes or {}).get(b.recipe_id)
            if not ra or not rb:
                continue
            pa, pb = primary_protein(ra), primary_protein(rb)
            if pa and pb and pa == pb and (
                a.day_index == b.day_index or b.day_index == a.day_index + 1
            ):
                consec += 1

        quick = 0
        if recipes:
            for m in cooks:
                r = recipes.get(m.recipe_id)
                if r and r.total_time_minutes <= 30:
                    quick += 1

        leftovers = sum(1 for m in plan.meals if m.is_leftover)
        batch_usage = sum(1 for c in plan.cooking_instances if c.servings_cooked > 1)
        cooking_events = len(plan.cooking_instances)

        aligned = 0
        for m in cooks:
            if m.day_index in context.cook_days or not context.cook_days:
                aligned += 1
        cook_align = aligned / max(1, len(cooks))

        ing_counter: Counter[str] = Counter()
        if recipes:
            for m in plan.meals:
                r = recipes.get(m.recipe_id)
                if r:
                    ing_counter.update(recipe_ingredient_ids(r))
        reused = sum(1 for c in ing_counter.values() if c >= 2)
        ing_reuse = reused / max(1, len(ing_counter))

        verified_ratio = None
        if quality_by_recipe is not None and plan.meals:
            verified = sum(
                1
                for m in plan.meals
                if quality_by_recipe.get(m.recipe_id) == "source_verified"
            )
            verified_ratio = verified / len(plan.meals)

        avg_sel = (
            sum(m.selection_score for m in plan.meals) / len(plan.meals)
            if plan.meals
            else 0.0
        )

        return WeeklyPlanEvaluation(
            slot_coverage=coverage,
            unique_recipe_ratio=unique_ratio,
            exact_repeat_count=exact_repeats,
            protein_diversity=protein_div,
            consecutive_protein_repeats=consec,
            quick_meal_count=quick,
            batch_usage=batch_usage,
            leftover_usage=leftovers,
            cooking_events=cooking_events,
            cook_day_alignment=cook_align,
            ingredient_reuse=ing_reuse,
            source_verified_ratio=verified_ratio,
            average_selector_score=avg_sel,
            weekly_score=plan.score,
            extras={
                "status": plan.status.value,
                "meals": len(plan.meals),
                "required_slots": len(required),
            },
        )
