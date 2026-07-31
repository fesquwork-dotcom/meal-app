import pytest

from menu_models import MenuPlan
from strategy.builder import StrategyBuilder
from strategy.compliance import validate_menu_against_strategy
from strategy.exceptions import StrategyComplianceError
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict, clone_menu


def _strategy(**overrides):
    profile = {
        "goal": "home",
        "days": 3,
        "budget": 3000,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "cooktime": "fast",
        "allergies": "нет",
    }
    profile.update(overrides)
    return StrategyBuilder().build(profile)


def _menu(**kwargs) -> MenuPlan:
    strategy = kwargs.pop("strategy", None)
    menu_dict = build_valid_menu_dict(**kwargs)
    if strategy is not None:
        menu_dict = annotate_cooking_metadata(menu_dict, strategy)
    return MenuPlan.model_validate(menu_dict)


def test_valid_menu_passes_compliance():
    strategy = _strategy()
    menu = _menu(days=3, cooktime="15 мин", meal_types=["breakfast", "lunch", "dinner"], strategy=strategy)
    validate_menu_against_strategy(menu, strategy)


def test_wrong_day_count_rejected():
    strategy = _strategy(days=3)
    menu = _menu(days=2, cooktime="15 мин", strategy=strategy)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_menu_against_strategy(menu, strategy)

    assert any(code == "STRATEGY_DAYS_COUNT_MISMATCH" for code in exc_info.value.issue_codes)


def test_missing_meal_type_rejected():
    strategy = _strategy(days=1, meal_types=["breakfast", "dinner"])
    menu_dict = annotate_cooking_metadata(
        build_valid_menu_dict(days=1, meal_types=["breakfast", "dinner"], cooktime="15 мин"),
        strategy,
    )
    menu_dict["days_plan"][0]["meals"] = [
        {"type": "breakfast", "recipe_name": menu_dict["days_plan"][0]["meals"][0]["recipe_name"]}
    ]
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_menu_against_strategy(menu, strategy)

    assert "STRATEGY_MEAL_TYPE_MISSING" in exc_info.value.issue_codes


def test_unexpected_meal_type_rejected():
    strategy = _strategy(days=1, meal_types=["breakfast", "dinner"])
    menu_dict = annotate_cooking_metadata(
        build_valid_menu_dict(days=1, meal_types=["breakfast", "dinner"], cooktime="15 мин"),
        strategy,
    )
    menu_dict["days_plan"][0]["meals"].append(
        {"type": "lunch", "recipe_name": "Борщ"}
    )
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_menu_against_strategy(menu, strategy)

    assert "STRATEGY_MEAL_TYPE_UNEXPECTED" in exc_info.value.issue_codes


def test_excluded_product_in_ingredient_rejected():
    strategy = _strategy(days=1, allergies="орехи")
    menu_dict = annotate_cooking_metadata(
        build_valid_menu_dict(days=1, cooktime="15 мин"),
        strategy,
    )
    menu_dict["recipes"][0]["ingredients"][0]["name"] = "арахис"
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_menu_against_strategy(menu, strategy)

    assert "STRATEGY_EXCLUDED_PRODUCT" in exc_info.value.issue_codes
    assert exc_info.value.paths[0] is not None


def test_cooking_time_exceeded_rejected():
    strategy = _strategy(days=1, cooktime="fast")
    menu_dict = annotate_cooking_metadata(
        build_valid_menu_dict(days=1, cooktime="60 минут"),
        strategy,
    )
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_menu_against_strategy(menu, strategy)

    assert "STRATEGY_COOKING_TIME_EXCEEDED" in exc_info.value.issue_codes


def test_compliance_error_has_stable_code_and_path():
    strategy = _strategy(days=1)
    menu_dict = annotate_cooking_metadata(
        build_valid_menu_dict(days=1, cooktime="15 мин"),
        strategy,
    )
    menu_dict["recipes"][0]["cook_time"] = "90 минут"
    menu = MenuPlan.model_validate(menu_dict)

    with pytest.raises(StrategyComplianceError) as exc_info:
        validate_menu_against_strategy(menu, strategy)

    assert exc_info.value.issue_codes
    assert exc_info.value.messages
    assert exc_info.value.paths


def test_validator_does_not_mutate_menu_plan():
    strategy = _strategy(days=1)
    menu_dict = annotate_cooking_metadata(
        build_valid_menu_dict(days=1, cooktime="15 мин"),
        strategy,
    )
    before = clone_menu(menu_dict)
    menu = MenuPlan.model_validate(menu_dict)

    validate_menu_against_strategy(menu, strategy)

    assert menu.model_dump() == MenuPlan.model_validate(before).model_dump()


def test_unparseable_cook_time_does_not_false_positive():
    strategy = _strategy(days=1, cooktime="fast")
    menu_dict = annotate_cooking_metadata(build_valid_menu_dict(days=1), strategy)
    for recipe in menu_dict["recipes"]:
        recipe["cook_time"] = "быстро"
    menu = MenuPlan.model_validate(menu_dict)

    validate_menu_against_strategy(menu, strategy)
