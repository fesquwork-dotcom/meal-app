import pytest

from menu_models import DayMeal, MenuPlan
from strategy.builder import StrategyBuilder
from strategy.cooking_compliance import validate_cooking_contract
from strategy.exceptions import StrategyComplianceError
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict, clone_menu


def _strategy(**overrides):
    profile = {
        "goal": "home",
        "days": 5,
        "budget": 5000,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "cooktime": "medium",
        "allergies": "нет",
    }
    profile.update(overrides)
    return StrategyBuilder().build(profile)


def _menu_dict(strategy, **kwargs):
    return annotate_cooking_metadata(build_valid_menu_dict(**kwargs), strategy)


def test_valid_cooking_only_on_cook_days_passes():
    strategy = _strategy()
    menu = MenuPlan.model_validate(_menu_dict(strategy, days=5))
    validate_cooking_contract(menu, strategy)


def test_new_cooking_outside_cook_day_rejected():
    strategy = _strategy()
    menu_dict = _menu_dict(strategy, days=5)
    menu_dict["days_plan"][1]["meals"][2]["requires_cooking"] = True
    menu_dict["days_plan"][1]["meals"][2]["prepared_on_day"] = 2
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_cooking_contract(menu, strategy)

    assert "STRATEGY_COOKING_OUTSIDE_COOK_DAY" in exc_info.value.issue_codes


def test_reheat_outside_cook_day_passes():
    strategy = _strategy()
    menu_dict = _menu_dict(strategy, days=5)
    meal = menu_dict["days_plan"][1]["meals"][2]
    meal["requires_cooking"] = False
    meal["prepared_on_day"] = 1
    meal["uses_leftovers"] = True
    meal["source_meal_id"] = "day1_dinner"
    menu = MenuPlan.model_validate(menu_dict)

    validate_cooking_contract(menu, strategy)


def test_prepared_day_out_of_range_rejected():
    strategy = _strategy(days=3, cooktime="fast")
    menu_dict = _menu_dict(strategy, days=3)
    menu_dict["days_plan"][0]["meals"][0]["prepared_on_day"] = 99
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_cooking_contract(menu, strategy)

    assert "STRATEGY_PREPARED_DAY_OUT_OF_RANGE" in exc_info.value.issue_codes


def test_prepared_day_in_future_rejected():
    strategy = _strategy(days=3, cooktime="fast")
    menu_dict = _menu_dict(strategy, days=3)
    menu_dict["days_plan"][1]["meals"][0]["prepared_on_day"] = 3
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_cooking_contract(menu, strategy)

    assert "STRATEGY_PREPARED_IN_FUTURE" in exc_info.value.issue_codes


def test_duplicate_meal_id_rejected():
    strategy = _strategy(days=3, cooktime="fast")
    menu_dict = _menu_dict(strategy, days=3)
    menu_dict["days_plan"][1]["meals"][0]["meal_id"] = "day1_breakfast"
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_cooking_contract(menu, strategy)

    assert "STRATEGY_MEAL_ID_DUPLICATE" in exc_info.value.issue_codes


def test_missing_meal_id_rejected():
    strategy = _strategy(days=1, cooktime="fast")
    menu_dict = _menu_dict(strategy, days=1)
    del menu_dict["days_plan"][0]["meals"][0]["meal_id"]
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_cooking_contract(menu, strategy)

    assert "STRATEGY_MEAL_ID_MISSING" in exc_info.value.issue_codes


def test_missing_source_meal_id_rejected():
    strategy = _strategy()
    menu_dict = _menu_dict(strategy, days=5)
    meal = menu_dict["days_plan"][1]["meals"][1]
    meal["uses_leftovers"] = True
    meal["requires_cooking"] = False
    meal["source_meal_id"] = None
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_cooking_contract(menu, strategy)

    assert "STRATEGY_LEFTOVER_SOURCE_MISSING" in exc_info.value.issue_codes


def test_self_reference_rejected():
    strategy = _strategy(days=3, cooktime="fast")
    menu_dict = _menu_dict(strategy, days=3)
    meal = menu_dict["days_plan"][0]["meals"][0]
    meal["source_meal_id"] = meal["meal_id"]
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_cooking_contract(menu, strategy)

    assert "STRATEGY_SOURCE_MEAL_SELF_REFERENCE" in exc_info.value.issue_codes


def test_source_cycle_rejected():
    strategy = _strategy(days=3, cooktime="fast")
    menu_dict = _menu_dict(strategy, days=3)
    first = menu_dict["days_plan"][0]["meals"][0]
    second = menu_dict["days_plan"][0]["meals"][1]
    first["source_meal_id"] = second["meal_id"]
    second["source_meal_id"] = first["meal_id"]
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_cooking_contract(menu, strategy)

    assert "STRATEGY_SOURCE_MEAL_CYCLE" in exc_info.value.issue_codes


def test_valid_leftover_link_passes():
    strategy = _strategy()
    menu_dict = _menu_dict(strategy, days=5)
    menu = MenuPlan.model_validate(menu_dict)
    validate_cooking_contract(menu, strategy)


def test_leftover_source_from_future_rejected():
    strategy = _strategy()
    menu_dict = _menu_dict(strategy, days=5)
    meal = menu_dict["days_plan"][1]["meals"][1]
    meal["source_meal_id"] = "day5_dinner"
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_cooking_contract(menu, strategy)

    assert "STRATEGY_LEFTOVER_SOURCE_NOT_EARLIER" in exc_info.value.issue_codes


def test_leftover_with_requires_cooking_rejected():
    strategy = _strategy()
    menu_dict = _menu_dict(strategy, days=5)
    meal = menu_dict["days_plan"][1]["meals"][1]
    meal["uses_leftovers"] = True
    meal["requires_cooking"] = True
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_cooking_contract(menu, strategy)

    assert "STRATEGY_LEFTOVER_REQUIRES_NEW_COOKING" in exc_info.value.issue_codes


def test_cooking_validator_does_not_mutate_menu():
    strategy = _strategy(days=3, cooktime="fast")
    menu_dict = _menu_dict(strategy, days=3)
    before = clone_menu(menu_dict)
    menu = MenuPlan.model_validate(menu_dict)

    validate_cooking_contract(menu, strategy)

    assert menu.model_dump() == MenuPlan.model_validate(before).model_dump()
