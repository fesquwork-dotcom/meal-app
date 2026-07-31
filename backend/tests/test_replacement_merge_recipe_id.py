"""Tests for replacement merge with recipe_id keys."""

from __future__ import annotations

from copy import deepcopy

from menu_models import BasketCategory, BasketItem, DayMeal, DayPlan, MenuPlan, Recipe, RecipeIngredient
from strategy.replacement_context import ReplacementContext, TargetMealContext
from strategy.replacement_merge import merge_replacement
from strategy.replacement_models import MealReplacementItem, ReplacementLLMResponse
from strategy.cooking_compliance import MealRef
from tests.test_replace_meal_api import _build_strategy_menu  # noqa: F401


def _simple_menu() -> MenuPlan:
    return MenuPlan(
        summary="Тест",
        total_cost=1000,
        plan_start_date="2026-01-01",
        strategy_id="strat-1",
        days_plan=[
            DayPlan(
                day="День 1",
                meals=[
                    DayMeal(
                        type="dinner",
                        recipe_name="Старая запеканка",
                        recipe_id="recipe_day1_dinner",
                        cooking_instance_id="cook_day1_dinner",
                        meal_id="day1_dinner",
                        requires_cooking=True,
                        prepared_on_day=1,
                    ),
                    DayMeal(
                        type="lunch",
                        recipe_name="Овсянка",
                        recipe_id="recipe_day1_lunch",
                        meal_id="day1_lunch",
                    ),
                ],
            ),
            DayPlan(
                day="День 2",
                meals=[
                    DayMeal(
                        type="dinner",
                        recipe_name="Овсянка",
                        recipe_id="recipe_day2_dinner",
                        meal_id="day2_dinner",
                    )
                ],
            ),
        ],
        recipes=[
            Recipe(
                name="Старая запеканка",
                recipe_id="recipe_day1_dinner",
                ingredients=[
                    RecipeIngredient(name="Картофель", amount="500 г", contribution="purchase")
                ],
                steps=["Запечь"],
            ),
            Recipe(
                name="Овсянка",
                recipe_id="recipe_day1_lunch",
                ingredients=[
                    RecipeIngredient(name="Овсянка", amount="100 г", contribution="purchase")
                ],
                steps=["Варить"],
            ),
            Recipe(
                name="Овсянка",
                recipe_id="recipe_day2_dinner",
                ingredients=[
                    RecipeIngredient(name="Овсянка", amount="100 г", contribution="purchase")
                ],
                steps=["Варить"],
            ),
        ],
        basket=[
            BasketCategory(
                category="Продукты",
                items=[
                    BasketItem(name="Картофель", weight="500 г", price=100),
                    BasketItem(name="Овсянка", weight="200 г", price=80),
                    BasketItem(name="Творог", weight="300 г", price=120),
                ],
            )
        ],
    )


def _context(menu: MenuPlan) -> ReplacementContext:
    target_ref = MealRef(day_index=0, meal_index=0, meal=menu.days_plan[0].meals[0])
    return ReplacementContext(
        strategy=None,  # type: ignore[arg-type]
        record=None,  # type: ignore[arg-type]
        menu_plan=menu,
        target=TargetMealContext(
            meal_ref=target_ref,
            day_number=1,
            recipe=menu.recipes[0],
            downstream_refs=(),
        ),
        validation_request=None,  # type: ignore[arg-type]
    )


def test_replacement_preserves_target_cooking_instance_id():
    menu = _simple_menu()
    target_instance = menu.days_plan[0].meals[0].cooking_instance_id or "cook_day1_dinner"
    menu.days_plan[0].meals[0] = menu.days_plan[0].meals[0].model_copy(
        update={"cooking_instance_id": target_instance}
    )
    llm = ReplacementLLMResponse(
        replacement=MealReplacementItem(
            meal=DayMeal(
                type="dinner",
                recipe_name="Новая запеканка",
                meal_id="day1_dinner",
                requires_cooking=True,
                prepared_on_day=1,
            ),
            recipe=Recipe(
                name="Новая запеканка",
                ingredients=[
                    RecipeIngredient(name="Творог", amount="300 г", contribution="purchase")
                ],
                steps=["Запечь"],
            ),
        )
    )

    merged = merge_replacement(_context(menu), llm)
    assert merged.days_plan[0].meals[0].cooking_instance_id == target_instance


def test_replacement_preserves_target_recipe_id():
    menu = _simple_menu()
    original = deepcopy(menu)
    llm = ReplacementLLMResponse(
        replacement=MealReplacementItem(
            meal=DayMeal(
                type="dinner",
                recipe_name="Новая запеканка",
                meal_id="day1_dinner",
                requires_cooking=True,
                prepared_on_day=1,
            ),
            recipe=Recipe(
                name="Новая запеканка",
                ingredients=[
                    RecipeIngredient(name="Творог", amount="300 г", contribution="purchase")
                ],
                steps=["Запечь"],
            ),
        )
    )

    merged = merge_replacement(_context(menu), llm)
    dinner = merged.days_plan[0].meals[0]
    assert dinner.recipe_id == "recipe_day1_dinner"
    assert merged.recipes[0].recipe_id == "recipe_day1_dinner"
    assert merged.recipes[0].name == "Новая запеканка"
    assert original.days_plan[0].meals[0].recipe_name == "Старая запеканка"


def test_orphan_old_recipe_removed_by_id_not_name():
    menu = _simple_menu()
    llm = ReplacementLLMResponse(
        replacement=MealReplacementItem(
            meal=DayMeal(
                type="dinner",
                recipe_name="Новая запеканка",
                meal_id="day1_dinner",
                requires_cooking=True,
                prepared_on_day=1,
            ),
            recipe=Recipe(
                name="Новая запеканка",
                ingredients=[
                    RecipeIngredient(name="Творог", amount="300 г", contribution="purchase")
                ],
                steps=["Запечь"],
            ),
        )
    )

    merged = merge_replacement(_context(menu), llm)
    ids = {recipe.recipe_id for recipe in merged.recipes}
    assert "recipe_day1_dinner" in ids
    assert len([recipe for recipe in merged.recipes if recipe.name == "Овсянка"]) == 2
