"""Select active recipe ingredients with cooking-instance-aware deduplication."""

from __future__ import annotations

from dataclasses import dataclass

from cooking_identity import menu_has_cooking_instances
from menu_models import DayMeal, MenuPlan, Recipe, RecipeIngredient
from recipe_identity import (
    effective_contribution,
    meal_has_contribution_roles,
    resolve_recipe_for_meal,
)
from shopping.models import BasketBuildWarning
from shopping.normalization import canonical_ingredient_name


@dataclass(frozen=True)
class ActiveIngredientContribution:
    meal: DayMeal
    recipe: Recipe
    ingredient: RecipeIngredient
    day_index: int


def _resolve_recipe(
    meal: DayMeal,
    recipes: list[Recipe],
    path: str,
) -> tuple[Recipe | None, BasketBuildWarning | None]:
    recipe, code = resolve_recipe_for_meal(meal, recipes, path=path)
    if code == "MEAL_RECIPE_AMBIGUOUS":
        return None, BasketBuildWarning(
            code="BASKET_AMBIGUOUS_RECIPE",
            message=f"Ambiguous recipe match for meal '{meal.recipe_name}'",
            path=path,
        )
    if recipe is None:
        return None, BasketBuildWarning(
            code="BASKET_RECIPE_NOT_FOUND",
            message=f"No recipe match for meal '{meal.recipe_name}'",
            path=path,
        )
    return recipe, None


def _dedupe_key(
    meal: DayMeal,
    recipe: Recipe,
    ingredient: RecipeIngredient,
    *,
    use_instance_dedup: bool,
) -> str:
    canonical = canonical_ingredient_name(ingredient.name)
    if meal.uses_leftovers:
        meal_key = meal.meal_id or meal.recipe_name
        return f"leftover::{meal_key}::{canonical}"

    if use_instance_dedup and meal.cooking_instance_id:
        recipe_key = meal.recipe_id or recipe.recipe_id or recipe.name
        return f"instance::{recipe_key}::{meal.cooking_instance_id}::{canonical}"

    meal_key = meal.meal_id or meal.recipe_name
    return f"meal::{meal_key}::{canonical}"


def get_active_ingredient_contributions(
    menu: MenuPlan,
) -> tuple[list[ActiveIngredientContribution], list[BasketBuildWarning]]:
    """Returns purchase ingredients for basket building.

    Rules:
    - Source/independent cooking: dedupe by (recipe_id, cooking_instance_id, ingredient).
    - Leftover meals: purchase additions counted per meal_id.
    - Legacy menus without cooking_instance_id: per-meal counting (no instance dedupe).
    """
    contributions: list[ActiveIngredientContribution] = []
    warnings: list[BasketBuildWarning] = []
    use_instance_dedup = menu_has_cooking_instances(menu)
    seen_keys: set[str] = set()

    for day_index, day in enumerate(menu.days_plan):
        for meal_index, meal in enumerate(day.meals):
            path = f"days_plan[{day_index}].meals[{meal_index}]"

            recipe, warning = _resolve_recipe(meal, menu.recipes, path)
            if warning is not None:
                warnings.append(warning)
                continue
            if recipe is None:
                continue

            if meal.uses_leftovers and not meal_has_contribution_roles(recipe):
                continue

            for ingredient in recipe.ingredients:
                role = effective_contribution(meal, ingredient)
                if role != "purchase":
                    continue

                key = _dedupe_key(
                    meal,
                    recipe,
                    ingredient,
                    use_instance_dedup=use_instance_dedup,
                )
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                contributions.append(
                    ActiveIngredientContribution(
                        meal=meal,
                        recipe=recipe,
                        ingredient=ingredient,
                        day_index=day_index,
                    )
                )

    return contributions, warnings


def get_referenced_recipe_ids(menu: MenuPlan) -> set[str]:
    ids: set[str] = set()
    for day in menu.days_plan:
        for meal in day.meals:
            if meal.recipe_id:
                ids.add(meal.recipe_id)
    return ids
