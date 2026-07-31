import json

import pytest
from pydantic import ValidationError

from strategy.models import WeeklyStrategy


def _sample_strategy_dict() -> dict[str, object]:
    return {
        "strategy_version": 1,
        "goal": "home",
        "days": 5,
        "budget": 3000.0,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "meals_per_day": 3,
        "cook_days": [1, 3, 5],
        "shopping_days": [1, 4],
        "leftovers_enabled": True,
        "repeat_breakfasts": False,
        "repeat_lunches": False,
        "repeat_dinners": False,
        "preferred_proteins": ["any"],
        "excluded_products": ["орехи"],
        "cooking_time_limit": 45,
        "generated_at": "2026-03-10T12:00:00+00:00",
    }


def test_weekly_strategy_defaults_strategy_version_to_two():
    payload = _sample_strategy_dict()
    del payload["strategy_version"]

    strategy = WeeklyStrategy.from_dict(payload)

    assert strategy.strategy_version == 5


def test_weekly_strategy_serializes_to_json():
    strategy = WeeklyStrategy.from_dict(_sample_strategy_dict())

    payload = json.loads(strategy.to_json())

    assert payload["strategy_version"] == 1
    assert payload["meal_types"] == ["breakfast", "lunch", "dinner"]
    assert payload["meals_per_day"] == 3
    assert payload["cook_days"] == [1, 3, 5]
    assert payload["excluded_products"] == ["орехи"]


def test_weekly_strategy_deserializes_from_json_roundtrip():
    original = WeeklyStrategy.from_dict(_sample_strategy_dict())
    restored = WeeklyStrategy.from_json(original.to_json())

    assert restored == original


def test_weekly_strategy_from_dict_ignores_extra_fields():
    payload = {**_sample_strategy_dict(), "unexpected": "value"}
    strategy = WeeklyStrategy.from_dict(payload)

    assert strategy.goal == "home"
    assert not hasattr(strategy, "unexpected")


def test_weekly_strategy_rejects_empty_cook_days():
    payload = _sample_strategy_dict()
    payload["cook_days"] = []

    with pytest.raises(ValidationError):
        WeeklyStrategy.from_dict(payload)


def test_weekly_strategy_rejects_unknown_goal():
    payload = _sample_strategy_dict()
    payload["goal"] = "brunch"

    with pytest.raises(ValidationError):
        WeeklyStrategy.from_dict(payload)


def test_weekly_strategy_sorts_day_lists_without_duplicates():
    payload = _sample_strategy_dict()
    payload["cook_days"] = [5, 1, 3, 1]
    payload["shopping_days"] = [4, 1, 4]

    strategy = WeeklyStrategy.from_dict(payload)

    assert strategy.cook_days == [1, 3, 5]
    assert strategy.shopping_days == [1, 4]


def test_weekly_strategy_rejects_meals_per_day_mismatch():
    payload = _sample_strategy_dict()
    payload["meals_per_day"] = 2

    with pytest.raises(ValidationError):
        WeeklyStrategy.from_dict(payload)


def test_weekly_strategy_rejects_duplicate_meal_types():
    payload = _sample_strategy_dict()
    payload["meal_types"] = ["breakfast", "breakfast"]

    with pytest.raises(ValidationError):
        WeeklyStrategy.from_dict(payload)


def test_weekly_strategy_rejects_day_outside_planning_period():
    payload = _sample_strategy_dict()
    payload["cook_days"] = [1, 6]

    with pytest.raises(ValidationError):
        WeeklyStrategy.from_dict(payload)


def test_weekly_strategy_rejects_negative_budget():
    payload = _sample_strategy_dict()
    payload["budget"] = -1

    with pytest.raises(ValidationError):
        WeeklyStrategy.from_dict(payload)


def test_weekly_strategy_normalizes_empty_strings_in_lists():
    payload = _sample_strategy_dict()
    payload["preferred_proteins"] = ["", "any", " "]
    payload["excluded_products"] = ["", "орехи", "  "]

    strategy = WeeklyStrategy.from_dict(payload)

    assert strategy.preferred_proteins == ["any"]
    assert strategy.excluded_products == ["орехи"]
