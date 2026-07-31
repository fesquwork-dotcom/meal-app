import pytest

from menu_models import DayMeal, MenuPlan
from tests.menu_fixtures import build_valid_menu_dict


def test_legacy_meal_without_cooking_fields_loads():
    menu_dict = build_valid_menu_dict(days=1)
    menu = MenuPlan.model_validate(menu_dict)
    meal = menu.days_plan[0].meals[0]

    assert meal.meal_id is None
    assert meal.requires_cooking is None
    assert meal.prepared_on_day is None
    assert meal.uses_leftovers is False
    assert meal.source_meal_id is None


def test_strategy_aware_meal_serializes_cooking_fields():
    menu_dict = build_valid_menu_dict(days=1)
    menu_dict["days_plan"][0]["meals"][0].update(
        {
            "meal_id": "day1_breakfast",
            "requires_cooking": False,
            "prepared_on_day": 1,
            "uses_leftovers": False,
            "source_meal_id": None,
        }
    )
    menu = MenuPlan.model_validate(menu_dict)
    dumped = menu.model_dump()

    assert dumped["days_plan"][0]["meals"][0]["meal_id"] == "day1_breakfast"
    assert dumped["days_plan"][0]["meals"][0]["requires_cooking"] is False
    assert dumped["days_plan"][0]["meals"][0]["prepared_on_day"] == 1


def test_meal_id_and_source_meal_id_persist():
    menu_dict = build_valid_menu_dict(days=2)
    menu_dict["days_plan"][0]["meals"][2].update(
        {
            "meal_id": "day1_dinner",
            "requires_cooking": True,
            "prepared_on_day": 1,
        }
    )
    menu_dict["days_plan"][1]["meals"][1].update(
        {
            "meal_id": "day2_lunch",
            "requires_cooking": False,
            "prepared_on_day": 1,
            "uses_leftovers": True,
            "source_meal_id": "day1_dinner",
        }
    )
    menu = MenuPlan.model_validate(menu_dict)

    assert menu.days_plan[1].meals[1].source_meal_id == "day1_dinner"


def test_prepared_on_day_must_be_positive():
    with pytest.raises(ValueError):
        DayMeal.model_validate(
            {
                "type": "breakfast",
                "recipe_name": "Овсянка",
                "prepared_on_day": 0,
            }
        )


def test_empty_meal_id_rejected():
    with pytest.raises(ValueError):
        DayMeal.model_validate(
            {
                "type": "breakfast",
                "recipe_name": "Овсянка",
                "meal_id": "   ",
            }
        )


def test_json_round_trip_preserves_optional_cooking_fields():
    menu_dict = build_valid_menu_dict(days=1)
    menu_dict["days_plan"][0]["meals"][0]["meal_id"] = "day1_breakfast"
    menu_dict["days_plan"][0]["meals"][0]["requires_cooking"] = True
    menu_dict["days_plan"][0]["meals"][0]["prepared_on_day"] = 1

    first = MenuPlan.model_validate(menu_dict)
    second = MenuPlan.model_validate(first.model_dump())

    assert first == second


def test_menu_plan_accepts_plan_start_date():
    menu_dict = build_valid_menu_dict(days=1)
    menu_dict["plan_start_date"] = "2026-07-13"

    menu = MenuPlan.model_validate(menu_dict)

    assert menu.plan_start_date.isoformat() == "2026-07-13"


def test_invalid_plan_start_date_rejected():
    menu_dict = build_valid_menu_dict(days=1)
    menu_dict["plan_start_date"] = "2026-02-31"

    with pytest.raises(ValueError):
        MenuPlan.model_validate(menu_dict)
