"""Tests for replacement context helpers."""

from datetime import date

import pytest

from strategy.builder import StrategyBuilder
from strategy.records import StrategyRecord
from strategy.replacement_context import (
    find_downstream_meals,
    find_meal_by_id,
    validate_menu_strategy_binding,
)
from strategy.replacement_exceptions import MealNotFoundError, MenuStrategyMismatchError
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict
from tests.strategy_fixtures import build_test_profile


def _strategy():
    return StrategyBuilder().build(build_test_profile(days=3))


def _strategy_menu(strategy, strategy_id: str = "strat-1"):
    menu = annotate_cooking_metadata(build_valid_menu_dict(days=strategy.days), strategy)
    menu["strategy_id"] = strategy_id
    menu["plan_start_date"] = "2026-07-13"
    return menu


def _record(strategy, strategy_id: str = "strat-1") -> StrategyRecord:
    return StrategyRecord(
        id=strategy_id,
        user_id=42,
        strategy_version=1,
        status="active",
        plan_start_date="2026-07-13",
        plan_days=strategy.days,
        strategy_json=strategy.to_json(),
        reason_codes_json=None,
        applied_memory_json=None,
        applied_cooking_preferences_json=None,
        applied_behavior_json=None,
        applied_planning_preferences_json=None,
        decision_context_json=None,
        decision_trace_json=None,
        decision_outcomes_json=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        completed_at=None,
        superseded_at=None,
    )


def test_find_meal_by_id():
    from menu_models import MenuPlan

    strategy = _strategy()
    menu = MenuPlan.model_validate(_strategy_menu(strategy))
    ref = find_meal_by_id(menu, "day1_breakfast")
    assert ref.meal.type == "breakfast"


def test_find_meal_not_found():
    from menu_models import MenuPlan

    strategy = _strategy()
    menu = MenuPlan.model_validate(_strategy_menu(strategy))
    with pytest.raises(MealNotFoundError):
        find_meal_by_id(menu, "missing")


def test_strategy_id_mismatch():
    from menu_models import MenuPlan

    strategy = _strategy()
    menu = MenuPlan.model_validate(_strategy_menu(strategy, strategy_id="other"))
    with pytest.raises(MenuStrategyMismatchError) as exc_info:
        validate_menu_strategy_binding(menu, "strat-1", _record(strategy), strategy)
    assert exc_info.value.code == "MENU_STRATEGY_ID_MISMATCH"
