"""Tests for cooking_instance_id assignment, validation, and basket deduplication."""

from __future__ import annotations

from menu_models import BasketCategory, BasketItem, DayMeal, DayPlan, MenuPlan, Recipe, RecipeIngredient
from cooking_identity import (
    assign_and_validate_cooking_instances,
    default_cooking_instance_id_for_meal,
    validate_cooking_instance_graph,
)
from shopping.basket_builder import build_basket_from_menu


def _oatmeal_recipe(recipe_id: str = "recipe_oatmeal") -> Recipe:
    return Recipe(
        name="Овсянка",
        recipe_id=recipe_id,
        ingredients=[
            RecipeIngredient(name="Овсянка", amount="100 г", contribution="purchase"),
            RecipeIngredient(name="Молоко", amount="200 мл", contribution="purchase"),
        ],
        steps=["Варить"],
    )


def _menu_one_recipe_two_cook_instances() -> MenuPlan:
    return MenuPlan(
        summary="Тест",
        total_cost=200,
        days_plan=[
            DayPlan(
                day="День 1",
                meals=[
                    DayMeal(
                        type="breakfast",
                        recipe_name="Овсянка",
                        recipe_id="recipe_oatmeal",
                        cooking_instance_id="cook_day1_breakfast",
                        meal_id="day1_breakfast",
                        requires_cooking=True,
                        prepared_on_day=1,
                    )
                ],
            ),
            DayPlan(
                day="День 4",
                meals=[
                    DayMeal(
                        type="breakfast",
                        recipe_name="Овсянка",
                        recipe_id="recipe_oatmeal",
                        cooking_instance_id="cook_day4_breakfast",
                        meal_id="day4_breakfast",
                        requires_cooking=True,
                        prepared_on_day=4,
                    )
                ],
            ),
        ],
        recipes=[_oatmeal_recipe()],
        basket=[
            BasketCategory(
                category="Продукты",
                items=[
                    BasketItem(name="Овсянка", weight="200 г", price=80),
                    BasketItem(name="Молоко", weight="400 мл", price=120),
                ],
            )
        ],
    )


def _menu_batch_chicken() -> MenuPlan:
    return MenuPlan(
        summary="Тест",
        total_cost=500,
        days_plan=[
            DayPlan(
                day="День 1",
                meals=[
                    DayMeal(
                        type="dinner",
                        recipe_name="Запечённая курица",
                        recipe_id="recipe_roast_chicken",
                        cooking_instance_id="batch_chicken_day1",
                        meal_id="day1_dinner",
                        requires_cooking=True,
                        prepared_on_day=1,
                    )
                ],
            ),
            DayPlan(
                day="День 2",
                meals=[
                    DayMeal(
                        type="lunch",
                        recipe_name="Боул с курицей",
                        recipe_id="recipe_chicken_bowl",
                        cooking_instance_id="batch_chicken_day1",
                        meal_id="day2_lunch",
                        uses_leftovers=True,
                        source_meal_id="day1_dinner",
                        prepared_on_day=1,
                    )
                ],
            ),
        ],
        recipes=[
            Recipe(
                name="Запечённая курица",
                recipe_id="recipe_roast_chicken",
                ingredients=[
                    RecipeIngredient(name="Курица", amount="500 г", contribution="purchase"),
                ],
                steps=["Запечь"],
            ),
            Recipe(
                name="Боул с курицей",
                recipe_id="recipe_chicken_bowl",
                ingredients=[
                    RecipeIngredient(name="Курица", amount="200 г", contribution="from_source"),
                    RecipeIngredient(name="Огурец", amount="1 шт", contribution="purchase"),
                ],
                steps=["Собрать"],
            ),
        ],
        basket=[
            BasketCategory(
                category="Продукты",
                items=[
                    BasketItem(name="Курица", weight="500 г", price=300),
                    BasketItem(name="Огурец", weight="1 шт", price=40),
                ],
            )
        ],
    )


def test_deterministic_cooking_instance_assignment():
    menu = _menu_batch_chicken()
    menu.days_plan[1].meals[0] = menu.days_plan[1].meals[0].model_copy(
        update={"cooking_instance_id": None}
    )
    updated, issues = assign_and_validate_cooking_instances(menu, strategy_aware=True)
    assert not issues
    assert updated.days_plan[1].meals[0].cooking_instance_id == "batch_chicken_day1"


def test_leftover_inherits_source_instance():
    menu = _menu_batch_chicken()
    menu.days_plan[1].meals[0] = menu.days_plan[1].meals[0].model_copy(
        update={"cooking_instance_id": None}
    )
    updated, _ = assign_and_validate_cooking_instances(menu, strategy_aware=True)
    assert updated.days_plan[1].meals[0].cooking_instance_id == "batch_chicken_day1"


def test_source_instance_mismatch_rejected():
    menu = _menu_batch_chicken()
    menu.days_plan[1].meals[0] = menu.days_plan[1].meals[0].model_copy(
        update={"cooking_instance_id": "wrong_instance"}
    )
    issues = validate_cooking_instance_graph(menu, strategy_aware=True)
    assert any(issue.code == "COOKING_INSTANCE_SOURCE_MISMATCH" for issue in issues)


def test_multiple_prepared_days_rejected():
    menu = _menu_batch_chicken()
    menu.days_plan[1].meals[0] = menu.days_plan[1].meals[0].model_copy(update={"prepared_on_day": 2})
    issues = validate_cooking_instance_graph(menu, strategy_aware=True)
    assert any(issue.code == "COOKING_INSTANCE_MULTIPLE_PREPARED_DAYS" for issue in issues)


def test_same_recipe_two_instances_doubles_basket():
    menu = _menu_one_recipe_two_cook_instances()
    result = build_basket_from_menu(menu)
    names = {item.name.lower() for category in result.basket for item in category.items}
    assert "овсянка" in names
    assert "молоко" in names
    total_lines = sum(len(c.items) for c in result.basket)
    assert total_lines == 2


def test_batch_instance_counts_source_once():
    menu = _menu_batch_chicken()
    result = build_basket_from_menu(menu)
    names = [item.name.lower() for category in result.basket for item in category.items]
    chicken_lines = [n for n in names if "куриц" in n]
    assert len(chicken_lines) == 1
    assert any("огурц" in n for n in names)


def test_default_instance_id_format():
    meal = DayMeal(type="dinner", recipe_name="Рыба", meal_id="day3_dinner")
    assert default_cooking_instance_id_for_meal(meal) == "cook_day3_dinner"


def test_assignment_does_not_mutate_input():
    menu = _menu_batch_chicken()
    original_instance = menu.days_plan[1].meals[0].cooking_instance_id
    menu.days_plan[1].meals[0] = menu.days_plan[1].meals[0].model_copy(
        update={"cooking_instance_id": None}
    )
    assign_and_validate_cooking_instances(menu, strategy_aware=True)
    assert menu.days_plan[1].meals[0].cooking_instance_id is None
    assert original_instance == "batch_chicken_day1"
