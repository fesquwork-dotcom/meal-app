"""Copy-on-write merge of replacement meals into MenuPlan."""

from __future__ import annotations

from copy import deepcopy

from menu_models import DayMeal, MenuPlan, Recipe
from recipe_identity import find_recipe_index_by_id, is_recipe_id_referenced, is_valid_recipe_id
from shopping.basket_builder import build_basket_from_menu
from shopping.exceptions import BasketPriceUnavailableError
from strategy.replacement_context import ReplacementContext
from strategy.replacement_exceptions import ReplacementPriceResolutionError
from strategy.replacement_models import ReplacementLLMResponse


def _enforce_meal_identity(
    meal: DayMeal,
    *,
    meal_id: str,
    meal_type: str,
    recipe_id: str | None,
    cooking_instance_id: str | None = None,
) -> DayMeal:
    updates: dict[str, object] = {"meal_id": meal_id, "type": meal_type}
    if recipe_id:
        updates["recipe_id"] = recipe_id
    if cooking_instance_id:
        updates["cooking_instance_id"] = cooking_instance_id
    return meal.model_copy(update=updates)


def _enforce_recipe_identity(recipe: Recipe, *, recipe_id: str) -> Recipe:
    return recipe.model_copy(update={"recipe_id": recipe_id})


def merge_replacement(
    context: ReplacementContext,
    llm_response: ReplacementLLMResponse,
) -> MenuPlan:
    menu_copy = deepcopy(context.menu_plan)
    target_id = context.target.meal_ref.meal.meal_id
    target_type = context.target.meal_ref.meal.type
    target_recipe_id = context.target.meal_ref.meal.recipe_id
    target_cooking_instance_id = context.target.meal_ref.meal.cooking_instance_id
    if not target_recipe_id:
        target_recipe_id = f"recipe_{target_id}"

    old_recipe_id = target_recipe_id

    changed_ids: list[str] = []

    target_recipe = _enforce_recipe_identity(
        llm_response.replacement.recipe,
        recipe_id=target_recipe_id,
    )
    target_meal = _enforce_meal_identity(
        llm_response.replacement.meal,
        meal_id=target_id,
        meal_type=target_type,
        recipe_id=target_recipe_id,
        cooking_instance_id=target_cooking_instance_id,
    )

    for day in menu_copy.days_plan:
        for meal_index, meal in enumerate(day.meals):
            if meal.meal_id == target_id:
                day.meals[meal_index] = target_meal
                changed_ids.append(target_id)

    recipes = list(menu_copy.recipes)
    recipe_index = find_recipe_index_by_id(recipes, target_recipe_id)
    if recipe_index is None:
        recipes.append(target_recipe)
    else:
        recipes[recipe_index] = target_recipe

    allowed_affected_ids = {ref.meal.meal_id for ref in context.target.downstream_refs}

    for affected in llm_response.affected_meals:
        affected_id = affected.meal.meal_id
        if not affected_id or affected_id not in allowed_affected_ids:
            raise ValueError(f"Unexpected affected meal_id '{affected_id}'")

        expected_ref = next(
            ref for ref in context.target.downstream_refs if ref.meal.meal_id == affected_id
        )
        affected_recipe_id = expected_ref.meal.recipe_id or (
            f"recipe_{expected_ref.meal.meal_id}" if expected_ref.meal.meal_id else None
        )
        enforced_recipe = affected.recipe
        if affected_recipe_id and is_valid_recipe_id(affected_recipe_id):
            enforced_recipe = _enforce_recipe_identity(affected.recipe, recipe_id=affected_recipe_id)

        affected_cooking_instance_id = expected_ref.meal.cooking_instance_id
        enforced = _enforce_meal_identity(
            affected.meal,
            meal_id=expected_ref.meal.meal_id,
            meal_type=expected_ref.meal.type,
            recipe_id=affected_recipe_id,
            cooking_instance_id=affected_cooking_instance_id,
        )

        for day in menu_copy.days_plan:
            for meal_index, meal in enumerate(day.meals):
                if meal.meal_id == enforced.meal_id:
                    day.meals[meal_index] = enforced
                    if enforced.meal_id not in changed_ids:
                        changed_ids.append(enforced.meal_id)

        aff_index = (
            find_recipe_index_by_id(recipes, affected_recipe_id)
            if affected_recipe_id
            else None
        )
        if aff_index is None:
            recipes.append(enforced_recipe)
        else:
            recipes[aff_index] = enforced_recipe

    temp_plan = menu_copy.model_copy(update={"recipes": recipes})
    if old_recipe_id and not is_recipe_id_referenced(temp_plan, old_recipe_id):
        recipes = [recipe for recipe in recipes if recipe.recipe_id != old_recipe_id]

    merged_plan = menu_copy.model_copy(update={"recipes": recipes})

    try:
        basket_result = build_basket_from_menu(
            merged_plan,
            existing_basket=context.menu_plan.basket,
            require_all_prices=True,
        )
    except BasketPriceUnavailableError as exc:
        raise ReplacementPriceResolutionError(exc.unresolved) from exc

    return merged_plan.model_copy(
        update={
            "basket": basket_result.basket,
            "total_cost": float(basket_result.total_cost or 0),
            "strategy_id": context.menu_plan.strategy_id,
            "plan_start_date": context.menu_plan.plan_start_date,
            "summary": context.menu_plan.summary,
        }
    )
