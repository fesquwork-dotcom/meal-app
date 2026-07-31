import math

import pytest

from menu_models import MenuPlan
from menu_validation import MenuValidationRequest, validate_menu_plan
from tests.menu_fixtures import build_valid_menu_dict, clone_menu


def _request(**overrides) -> MenuValidationRequest:
    base = {
        "days": 3,
        "budget": 3000.0,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "meals_per_day": 3,
        "persons": 2,
        "cooktime": "medium",
        "allergies": "нет",
    }
    base.update(overrides)
    return MenuValidationRequest(**base)


def _validate(menu_dict: dict[str, object], **request_overrides):
    menu_plan = MenuPlan.model_validate(menu_dict)
    return validate_menu_plan(menu_plan, _request(**request_overrides))


def test_valid_menu_passes():
    result = _validate(build_valid_menu_dict())
    assert result.is_valid is True
    assert result.menu_plan is not None
    assert result.errors == []


def test_wrong_day_count_fails():
    menu = build_valid_menu_dict(days=3)
    menu["days_plan"] = menu["days_plan"][:2]
    result = _validate(menu, days=3)
    assert not result.is_valid
    assert any(issue.code == "DAYS_COUNT_MISMATCH" for issue in result.errors)


def test_meal_without_recipe_fails():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["days_plan"][0]["meals"][0]["recipe_name"] = "Несуществующее блюдо"
    result = _validate(menu, days=1)
    assert not result.is_valid
    assert any(issue.code == "MEAL_RECIPE_MISSING" for issue in result.errors)


def test_ambiguous_recipe_match_fails():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["recipes"].append(
        {
            "name": "Овсянка",
            "emoji": "🥣",
            "cook_time": "10 мин",
            "kbju": "",
            "ingredients": [{"name": "овсянка", "amount": "100 г"}],
            "steps": ["Сварить"],
        }
    )
    result = _validate(menu, days=1)
    assert any(issue.code == "MEAL_RECIPE_AMBIGUOUS" for issue in result.warnings)


def test_ambiguous_recipe_match_fails_strategy_aware():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["recipes"].append(
        {
            "name": "Овсянка",
            "emoji": "🥣",
            "cook_time": "10 мин",
            "kbju": "",
            "ingredients": [{"name": "овсянка", "amount": "100 г"}],
            "steps": ["Сварить"],
        }
    )
    result = _validate(menu, days=1, strategy_aware=True)
    assert not result.is_valid
    assert any(issue.code == "MEAL_RECIPE_AMBIGUOUS" for issue in result.errors)


def test_unused_recipe_warning():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["recipes"].append(
        {
            "name": "Лишний суп",
            "emoji": "🍲",
            "cook_time": "30 мин",
            "kbju": "",
            "ingredients": [{"name": "вода", "amount": "1 л"}],
            "steps": ["Сварить"],
        }
    )
    menu["basket"][0]["items"].append({"name": "вода", "weight": "1 л", "price": 0})
    result = _validate(menu, days=1)
    assert result.is_valid
    assert any(issue.code == "RECIPE_UNUSED" for issue in result.warnings)


def test_budget_exceeded_fails():
    menu = clone_menu(build_valid_menu_dict())
    menu["total_cost"] = 5000
    for item in menu["basket"][0]["items"]:
        item["price"] = round(5000 / len(menu["basket"][0]["items"]), 2)
    result = _validate(menu, budget=3000)
    assert not result.is_valid
    assert any(issue.code == "BUDGET_EXCEEDED" for issue in result.errors)


def test_total_cost_mismatch_fails():
    menu = clone_menu(build_valid_menu_dict())
    menu["total_cost"] = 9999
    result = _validate(menu)
    assert not result.is_valid
    assert any(issue.code == "TOTAL_COST_MISMATCH" for issue in result.errors)


def test_allergen_in_ingredients_fails():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["recipes"][0]["ingredients"][0]["name"] = "молоко"
    result = _validate(menu, days=1, allergies="молоко")
    assert not result.is_valid
    assert any(issue.code == "ALLERGY_VIOLATION" for issue in result.errors)


def test_allergen_in_basket_fails():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["basket"][0]["items"][0]["name"] = "сыр"
    result = _validate(menu, days=1, allergies="молоко")
    assert not result.is_valid
    assert any(issue.code == "ALLERGY_VIOLATION" for issue in result.errors)


def test_cooktime_exceeded_fails():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["recipes"][0]["cook_time"] = "60 минут"
    result = _validate(menu, days=1, cooktime="fast")
    assert not result.is_valid
    assert any(issue.code == "COOKTIME_EXCEEDED" for issue in result.errors)


def test_cooktime_unparseable_warning():
    menu = clone_menu(build_valid_menu_dict(days=1))
    for recipe in menu["recipes"]:
        recipe["cook_time"] = "быстро"
    result = _validate(menu, days=1, cooktime="fast")
    assert result.is_valid
    assert any(issue.code == "COOKTIME_UNPARSEABLE" for issue in result.warnings)


def test_duplicate_meal_twice_warning():
    menu = clone_menu(build_valid_menu_dict(days=3))
    menu["days_plan"][1]["meals"][0]["recipe_name"] = menu["days_plan"][0]["meals"][0][
        "recipe_name"
    ]
    result = _validate(menu, days=3)
    assert result.is_valid
    assert any(issue.code == "MEAL_DUPLICATE_WARNING" for issue in result.warnings)


def test_duplicate_meal_three_times_error():
    menu = clone_menu(build_valid_menu_dict(days=3))
    repeated = menu["days_plan"][0]["meals"][0]["recipe_name"]
    menu["days_plan"][1]["meals"][1]["recipe_name"] = repeated
    menu["days_plan"][2]["meals"][2]["recipe_name"] = repeated
    result = _validate(menu, days=3)
    assert not result.is_valid
    assert any(issue.code == "MEAL_DUPLICATE_EXCESSIVE" for issue in result.errors)


def test_missing_basket_ingredient_warning():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["recipes"][0]["ingredients"].append({"name": "редька", "amount": "1 шт"})
    result = _validate(menu, days=1)
    assert result.is_valid
    assert any(issue.code == "BASKET_INGREDIENT_MISSING" for issue in result.warnings)


def test_pantry_staple_missing_no_warning():
    menu = clone_menu(build_valid_menu_dict(days=1))
    result = _validate(menu, days=1)
    salt_warnings = [
        issue
        for issue in result.warnings
        if issue.code == "BASKET_INGREDIENT_MISSING" and "Соль" in issue.message
    ]
    assert salt_warnings == []


def test_negative_price_rejected_by_schema():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["basket"][0]["items"][0]["price"] = -1
    with pytest.raises(Exception):
        MenuPlan.model_validate(menu)


def test_nan_price_rejected_by_schema():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["basket"][0]["items"][0]["price"] = math.nan
    with pytest.raises(Exception):
        MenuPlan.model_validate(menu)


def test_bool_price_rejected_by_schema():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["basket"][0]["items"][0]["price"] = True
    with pytest.raises(Exception):
        MenuPlan.model_validate(menu)


def test_empty_steps_rejected_by_schema():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["recipes"][0]["steps"] = [""]
    with pytest.raises(Exception):
        MenuPlan.model_validate(menu)


def test_empty_recipes_rejected_by_schema():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["recipes"] = []
    with pytest.raises(Exception):
        MenuPlan.model_validate(menu)


def test_infinity_total_cost_rejected_by_schema():
    menu = clone_menu(build_valid_menu_dict(days=1))
    menu["total_cost"] = math.inf
    with pytest.raises(Exception):
        MenuPlan.model_validate(menu)
