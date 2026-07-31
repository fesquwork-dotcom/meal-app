"""Tests for recipe_id assignment, validation, and ingredient contributions."""

from __future__ import annotations

from menu_models import BasketCategory, BasketItem, DayMeal, DayPlan, MenuPlan, Recipe, RecipeIngredient
from menu_validation import MenuValidationRequest, validate_menu_plan
from recipe_identity import (
    assign_and_validate_recipe_ids,
    build_recipe_usage_graph,
    effective_contribution,
    validate_ingredient_contributions,
    validate_recipe_graph,
)
from shopping.basket_builder import build_basket_from_menu
from tests.menu_fixtures import build_valid_menu_dict, clone_menu


def _validation_request(**kwargs) -> MenuValidationRequest:
    defaults = {
        "days": 3,
        "budget": 3000.0,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "meals_per_day": 3,
        "persons": 2,
        "cooktime": "medium",
        "allergies": "нет",
        "strategy_aware": False,
    }
    defaults.update(kwargs)
    return MenuValidationRequest(**defaults)


def _menu_with_ids() -> MenuPlan:
    return MenuPlan(
        summary="Тест",
        total_cost=420,
        days_plan=[
            DayPlan(
                day="День 1",
                meals=[
                    DayMeal(
                        type="dinner",
                        recipe_name="Курица",
                        recipe_id="recipe_day1_dinner",
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
                        recipe_name="Боул",
                        recipe_id="recipe_day2_lunch",
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
                name="Курица",
                recipe_id="recipe_day1_dinner",
                ingredients=[
                    RecipeIngredient(name="Куриная грудка", amount="500 г", contribution="purchase"),
                    RecipeIngredient(name="Соль", amount="по вкусу", contribution="pantry"),
                ],
                steps=["Запечь"],
            ),
            Recipe(
                name="Боул",
                recipe_id="recipe_day2_lunch",
                ingredients=[
                    RecipeIngredient(name="Курица", amount="200 г", contribution="from_source"),
                    RecipeIngredient(name="Огурец", amount="1 шт", contribution="purchase"),
                    RecipeIngredient(name="Помидор", amount="2 шт", contribution="purchase"),
                ],
                steps=["Собрать"],
            ),
        ],
        basket=[
            BasketCategory(
                category="Продукты",
                items=[
                    BasketItem(name="Куриная грудка", weight="500 г", price=300),
                    BasketItem(name="Огурец", weight="1 шт", price=40),
                    BasketItem(name="Помидор", weight="2 шт", price=80),
                ],
            )
        ],
    )


def test_unique_recipe_ids_pass_validation():
    menu = _menu_with_ids()
    issues = validate_recipe_graph(menu, strategy_aware=True)
    assert not any(issue.severity == "error" for issue in issues)


def test_duplicate_recipe_id_rejected():
    menu = _menu_with_ids()
    menu.recipes.append(
        Recipe(
            name="Дубликат",
            recipe_id="recipe_day1_dinner",
            ingredients=[RecipeIngredient(name="Рис", amount="100 г", contribution="purchase")],
            steps=["Варить"],
        )
    )
    issues = validate_recipe_graph(menu, strategy_aware=True)
    assert any(issue.code == "RECIPE_ID_DUPLICATE" for issue in issues)


def test_meal_missing_recipe_rejected():
    menu = _menu_with_ids()
    menu.days_plan[0].meals[0] = menu.days_plan[0].meals[0].model_copy(
        update={"recipe_id": "recipe_missing"}
    )
    issues = validate_recipe_graph(menu, strategy_aware=True)
    assert any(issue.code == "MEAL_RECIPE_NOT_FOUND" for issue in issues)


def test_same_name_different_ids_work():
    menu = _menu_with_ids()
    menu.recipes.append(
        Recipe(
            name="Курица",
            recipe_id="recipe_day3_dinner",
            ingredients=[RecipeIngredient(name="Курица", amount="400 г", contribution="purchase")],
            steps=["Жарить"],
        )
    )
    menu.days_plan[0].meals[0] = menu.days_plan[0].meals[0].model_copy(
        update={"recipe_id": "recipe_day1_dinner"}
    )
    updated, issues = assign_and_validate_recipe_ids(menu, strategy_aware=False)
    assert not any(issue.code == "RECIPE_ID_DUPLICATE" for issue in issues)
    ids = {recipe.recipe_id for recipe in updated.recipes if recipe.recipe_id}
    assert "recipe_day1_dinner" in ids
    assert "recipe_day3_dinner" in ids


def test_assignment_is_deterministic():
    raw = build_valid_menu_dict(days=1, meal_types=["breakfast"])
    menu = MenuPlan.model_validate(raw)
    first, _ = assign_and_validate_recipe_ids(menu, strategy_aware=False)
    second, _ = assign_and_validate_recipe_ids(menu, strategy_aware=False)
    assert first.days_plan[0].meals[0].recipe_id == second.days_plan[0].meals[0].recipe_id


def test_partial_leftover_basket_includes_fresh_ingredients():
    menu = _menu_with_ids()
    result = build_basket_from_menu(menu)

    names = [item.name.lower() for category in result.basket for item in category.items]
    assert any("курин" in name for name in names)
    assert any("огурц" in name for name in names)
    assert any("помидор" in name for name in names)
    assert not any("700" in item.weight for category in result.basket for item in category.items)


def test_from_source_not_in_basket():
    menu = _menu_with_ids()
    result = build_basket_from_menu(menu)
    names = [item.name.lower() for category in result.basket for item in category.items]
    chicken_lines = [name for name in names if "курин" in name or "куриц" in name]
    assert len(chicken_lines) == 1


def test_pantry_not_in_basket():
    menu = _menu_with_ids()
    result = build_basket_from_menu(menu)
    names = [item.name.lower() for category in result.basket for item in category.items]
    assert not any("соль" in name for name in names)


def test_from_source_without_source_meal_rejected():
    menu = _menu_with_ids()
    menu.days_plan[1].meals[0] = menu.days_plan[1].meals[0].model_copy(update={"source_meal_id": None})
    issues = validate_ingredient_contributions(menu, strategy_aware=True)
    assert any(issue.code == "INGREDIENT_FROM_SOURCE_WITHOUT_SOURCE_MEAL" for issue in issues)


def test_from_source_on_non_leftover_rejected():
    menu = _menu_with_ids()
    menu.days_plan[0].meals[0] = menu.days_plan[0].meals[0].model_copy(update={"uses_leftovers": False})
    menu.recipes[0].ingredients[0] = menu.recipes[0].ingredients[0].model_copy(
        update={"contribution": "from_source"}
    )
    issues = validate_ingredient_contributions(menu, strategy_aware=True)
    assert any(issue.code == "INGREDIENT_FROM_SOURCE_ON_NON_LEFTOVER" for issue in issues)


def test_leftover_without_from_source_rejected():
    menu = _menu_with_ids()
    menu.recipes[1].ingredients[0] = menu.recipes[1].ingredients[0].model_copy(
        update={"contribution": "purchase"}
    )
    issues = validate_ingredient_contributions(menu, strategy_aware=True)
    assert any(issue.code == "LEFTOVER_SOURCE_INGREDIENT_MISSING" for issue in issues)


def test_expensive_pantry_normalized_to_purchase():
    ingredient = RecipeIngredient(name="Лосось", amount="300 г", contribution="pantry")
    assert effective_contribution(
        DayMeal(type="dinner", recipe_name="Рыба"),
        ingredient,
    ) == "purchase"


def test_real_pantry_staple_accepted():
    ingredient = RecipeIngredient(name="Соль", amount="по вкусу", contribution="pantry")
    assert effective_contribution(
        DayMeal(type="dinner", recipe_name="Суп"),
        ingredient,
    ) == "pantry"


def test_recipe_usage_graph_index():
    menu = _menu_with_ids()
    graph = build_recipe_usage_graph(menu)
    assert "recipe_day1_dinner" in graph.recipe_id_to_meal_ids
    assert "recipe_day2_lunch" in graph.recipe_id_to_recipe


def test_strategy_aware_validation_requires_contributions():
    menu = _menu_with_ids()
    graph_issues = validate_recipe_graph(menu, strategy_aware=True)
    contribution_issues = validate_ingredient_contributions(menu, strategy_aware=True)
    assert not any(issue.severity == "error" for issue in graph_issues)
    assert not any(issue.severity == "error" for issue in contribution_issues)


def test_legacy_ambiguous_name_is_warning_not_error():
    menu_dict = clone_menu(build_valid_menu_dict(days=1, meal_types=["breakfast"]))
    menu_dict["recipes"].append(
        {
            "name": menu_dict["days_plan"][0]["meals"][0]["recipe_name"],
            "emoji": "🥣",
            "cook_time": "10 мин",
            "kbju": "",
            "ingredients": [{"name": "овсянка", "amount": "100 г"}],
            "steps": ["Сварить"],
        }
    )
    menu = MenuPlan.model_validate(menu_dict)

    result = validate_menu_plan(
        menu,
        _validation_request(days=1, meal_types=["breakfast"], meals_per_day=1),
    )
    assert any(w.code == "MEAL_RECIPE_AMBIGUOUS" for w in result.warnings)
