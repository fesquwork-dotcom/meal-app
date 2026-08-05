"""Hard weekly constraint checks for candidate actions."""

from __future__ import annotations

from dataclasses import dataclass

from recipes.enums import MealType, TagType
from recipes.models import Recipe
from recipes.planning.codes import PlannerViolationCode
from recipes.planning.context import WeeklyPlanningContext
from recipes.planning.relations import RelationIndex
from recipes.planning.slots import WeeklyMealSlot
from recipes.planning.weights import WeeklyPlannerConfig


@dataclass(frozen=True)
class ConstraintFailure:
    code: str
    detail: str = ""


def meal_type_supported(recipe: Recipe, meal_type: MealType) -> bool:
    return any(link.meal_type == meal_type for link in recipe.meal_types) or (
        recipe.primary_meal_type == meal_type
    )


def has_excluded_ingredient(recipe: Recipe, excluded: set[str]) -> bool:
    if not excluded:
        return False
    return any(ri.ingredient_id in excluded for ri in recipe.ingredients)


def has_excluded_protein(recipe: Recipe, excluded: set) -> bool:
    if not excluded:
        return False
    values = {p.value if hasattr(p, "value") else str(p) for p in excluded}
    tags = {
        t.tag_value
        for t in recipe.tags
        if t.tag_type == TagType.PROTEIN_SOURCE
    }
    return bool(tags & values)


def check_cook_action(
    *,
    recipe: Recipe,
    slot: WeeklyMealSlot,
    context: WeeklyPlanningContext,
    config: WeeklyPlannerConfig,
    relation_index: RelationIndex,
    previous_day_recipe_ids: set[str],
    independent_cook_counts: dict[str, int],
) -> ConstraintFailure | None:
    if not meal_type_supported(recipe, slot.meal_type):
        return ConstraintFailure(PlannerViolationCode.MEAL_TYPE_INVALID)
    if recipe.id in context.avoided_recipe_ids:
        return ConstraintFailure(PlannerViolationCode.AVOIDED_RECIPE)
    if has_excluded_ingredient(recipe, context.excluded_ingredient_ids):
        return ConstraintFailure(PlannerViolationCode.EXCLUDED_INGREDIENT)
    if has_excluded_protein(recipe, context.excluded_protein_sources):
        return ConstraintFailure(PlannerViolationCode.EXCLUDED_PROTEIN)
    if (
        context.max_cooking_time is not None
        and recipe.total_time_minutes > context.max_cooking_time
    ):
        return ConstraintFailure(PlannerViolationCode.TIME_LIMIT)
    if context.allowed_budget_classes is not None:
        allowed = {b.value for b in context.allowed_budget_classes}
        if recipe.budget_class.value not in allowed:
            return ConstraintFailure(PlannerViolationCode.BUDGET_CLASS)

    repeats = independent_cook_counts.get(recipe.id, 0)
    if repeats >= config.max_independent_recipe_repeats:
        return ConstraintFailure(PlannerViolationCode.RECIPE_REPEAT)

    for prev in previous_day_recipe_ids:
        if relation_index.has_avoid_consecutive(recipe.id, prev):
            return ConstraintFailure(
                PlannerViolationCode.AVOID_CONSECUTIVE_DAYS,
                detail=f"{recipe.id}<->{prev}",
            )

    if (
        not slot.is_cook_day
        and not config.allow_cook_day_miss
        and recipe.requires_cooking
    ):
        return ConstraintFailure("COOK_DAY_REQUIRED")

    return None


def check_leftover_action(
    *,
    recipe: Recipe,
    slot: WeeklyMealSlot,
    context: WeeklyPlanningContext,
    source_slot_order: int,
    slot_order: int,
    remaining_servings: int,
) -> ConstraintFailure | None:
    if not context.leftovers_enabled:
        return ConstraintFailure(PlannerViolationCode.LEFTOVER_DISABLED)
    if not slot.leftovers_allowed:
        return ConstraintFailure(PlannerViolationCode.LEFTOVER_DISABLED)
    if remaining_servings <= 0:
        return ConstraintFailure(PlannerViolationCode.LEFTOVER_OVERCONSUMED)
    if source_slot_order >= slot_order:
        return ConstraintFailure(PlannerViolationCode.LEFTOVER_BEFORE_SOURCE)
    if not meal_type_supported(recipe, slot.meal_type):
        return ConstraintFailure(PlannerViolationCode.MEAL_TYPE_INVALID)
    if has_excluded_ingredient(recipe, context.excluded_ingredient_ids):
        return ConstraintFailure(PlannerViolationCode.EXCLUDED_INGREDIENT)
    if has_excluded_protein(recipe, context.excluded_protein_sources):
        return ConstraintFailure(PlannerViolationCode.EXCLUDED_PROTEIN)
    return None
