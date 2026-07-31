import json
from datetime import datetime, timezone

import pytest

from strategy.builder import StrategyBuilder
from strategy.prompt import (
    build_strategy_prompt_section,
    build_strategy_system_section,
    strategy_to_prompt_dict,
)


def _strategy():
    return StrategyBuilder(clock=lambda: datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)).build(
        {
            "goal": "budget",
            "days": 7,
            "budget": 5000,
            "meal_types": ["breakfast", "lunch", "dinner"],
            "proteins": ["chicken", "fish"],
            "cooktime": "medium",
            "allergies": "орехи",
        }
    )


def test_strategy_to_prompt_dict_excludes_generated_at():
    strategy = _strategy()
    payload = strategy_to_prompt_dict(strategy)

    assert "generated_at" not in payload
    assert "meals_per_day" not in payload
    assert payload["strategy_version"] == 5
    assert payload["prefer_familiar_meals"] is False
    assert payload["prefer_faster_meals"] is False
    assert payload["availability_avoid_products"] == []
    assert payload["goal"] == "budget"
    assert payload["meal_types"] == ["breakfast", "lunch", "dinner"]
    assert payload["cook_days"] == [1, 3, 5, 7]
    assert payload["excluded_products"] == ["орехи"]
    assert payload["cooking_time_limit"] == 45


def test_build_strategy_prompt_section_contains_json_and_constraints():
    strategy = _strategy()
    section = build_strategy_prompt_section(strategy)

    assert "WEEKLY_STRATEGY" in section
    assert '"repeat_breakfasts": true' in section
    assert '"leftovers_enabled": true' in section
    assert '"cook_days"' in section
    assert "орехи" in section
    assert "None" not in section

    block = section.split("WEEKLY_STRATEGY (обязательный контракт, JSON):\n", 1)[1]
    block = block.split("\nДни периода")[0].strip()
    parsed = json.loads(block)
    assert parsed["shopping_days"] == [1, 4]


def test_build_strategy_system_section_forbids_strategy_changes():
    system = build_strategy_system_section()

    assert "обязательна" in system.lower() or "AUTHORITATIVE" in system
    assert "не переосмысливай" in system.lower() or "не противоречь" in system.lower()
    assert "cook_days" in system
    assert "leftovers_enabled" in system
    assert "cooking_time_limit" in system
    assert "availability_avoid_products" in system


def test_prompt_dict_has_stable_sorted_keys():
    strategy = _strategy()
    first = json.dumps(strategy_to_prompt_dict(strategy), sort_keys=True)
    second = json.dumps(strategy_to_prompt_dict(strategy), sort_keys=True)
    assert first == second
