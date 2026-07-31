"""Tests for strategy settings diff engine (Sprint 5.24)."""

from __future__ import annotations

from strategy.applied_cooking import AppliedCookingSettingsResponse
from strategy.applied_settings import AppliedSettingsResponse
from strategy.models import WeeklyStrategy
from strategy.settings_diff import build_strategy_settings_diff
from tests.strategy_fixtures import build_test_strategy


def _strategy(**overrides) -> WeeklyStrategy:
    return build_test_strategy(**overrides)


def _applied(
    *,
    limit: int = 45,
    faster: bool = False,
    source: str = "default",
) -> AppliedSettingsResponse:
    return AppliedSettingsResponse(
        cooking=AppliedCookingSettingsResponse(
            cooking_time_limit=limit,
            prefer_faster_meals=faster,
            preference_source=source,
        )
    )


def test_identical_strategies_no_changes():
    current = _strategy()
    diff = build_strategy_settings_diff(
        current,
        current.model_copy(deep=True),
        current_applied_settings=_applied(),
        next_applied_settings=_applied(),
    )
    assert diff.has_changes is False
    assert diff.changes == []
    assert diff.unchanged_count == 17
    assert diff.comparison_quality == "exact"


def test_budget_change():
    current = _strategy(budget=3000)
    next_ = _strategy(budget=5000)
    diff = build_strategy_settings_diff(
        current,
        next_,
        current_applied_settings=_applied(),
        next_applied_settings=_applied(),
    )
    assert diff.has_changes is True
    assert any(change.key == "budget" for change in diff.changes)
    budget_change = next(change for change in diff.changes if change.key == "budget")
    assert "3 000" in budget_change.description
    assert "5 000" in budget_change.description


def test_cooking_limit_change():
    current = _strategy(cooktime="medium")
    next_ = _strategy(cooktime="slow")
    diff = build_strategy_settings_diff(
        current,
        next_,
        current_applied_settings=_applied(limit=45),
        next_applied_settings=_applied(limit=90),
    )
    limit_change = next(change for change in diff.changes if change.key == "cooking_time_limit")
    assert "45" in limit_change.description
    assert "90" in limit_change.description


def test_faster_value_change():
    current = _strategy()
    next_ = _strategy(cooking_preferences={"prefer_faster_meals": False})
    current_applied = _applied(faster=True, source="memory")
    next_applied = _applied(faster=False, source="profile")
    diff = build_strategy_settings_diff(
        current,
        next_,
        current_applied_settings=current_applied,
        next_applied_settings=next_applied,
    )
    faster_change = next(change for change in diff.changes if change.key == "prefer_faster_meals")
    assert "включено" in faster_change.description
    assert "выключено" in faster_change.description


def test_faster_source_only_change():
    strategy = _strategy()
    current_applied = _applied(faster=True, source="memory")
    next_applied = _applied(faster=True, source="profile")
    diff = build_strategy_settings_diff(
        strategy,
        strategy.model_copy(deep=True),
        current_applied_settings=current_applied,
        next_applied_settings=next_applied,
    )
    source_change = next(
        change for change in diff.changes if change.key == "prefer_faster_meals_source"
    )
    assert source_change.change_type == "source_changed"
    assert "профиле" in source_change.description


def test_exclusion_count_added():
    current = _strategy()
    next_ = current.model_copy(deep=True)
    next_.excluded_products = [*current.excluded_products, "гречка"]
    diff = build_strategy_settings_diff(
        current,
        next_,
        current_applied_settings=_applied(),
        next_applied_settings=_applied(),
    )
    exclusion = next(change for change in diff.changes if change.key == "excluded_products")
    assert exclusion.change_type == "added"
    assert "ещё одно ограничение" in exclusion.description


def test_protein_removed():
    current = _strategy(proteins=["chicken", "fish"])
    next_ = _strategy(proteins=["chicken"])
    diff = build_strategy_settings_diff(
        current,
        next_,
        current_applied_settings=_applied(),
        next_applied_settings=_applied(),
    )
    protein_change = next(change for change in diff.changes if change.key == "preferred_proteins")
    assert protein_change.change_type == "removed"
    assert "рыба" in protein_change.description.lower()


def test_list_order_does_not_create_false_change():
    current = _strategy()
    next_ = current.model_copy(deep=True)
    next_.cook_days = list(reversed(current.cook_days))
    diff = build_strategy_settings_diff(
        current,
        next_,
        current_applied_settings=_applied(),
        next_applied_settings=_applied(),
    )
    assert not any(change.key == "cook_days" for change in diff.changes)


def test_stable_ordering_priority():
    current = _strategy(budget=3000, goal="home")
    next_ = _strategy(budget=5000, goal="budget")
    diff = build_strategy_settings_diff(
        current,
        next_,
        current_applied_settings=_applied(),
        next_applied_settings=_applied(),
    )
    keys = [change.key for change in diff.changes]
    assert keys.index("goal") < keys.index("budget")


def test_deterministic_repeated_result():
    current = _strategy(cooktime="fast")
    next_ = _strategy(cooktime="slow")
    first = build_strategy_settings_diff(
        current,
        next_,
        current_applied_settings=_applied(limit=20),
        next_applied_settings=_applied(limit=90),
    )
    second = build_strategy_settings_diff(
        current,
        next_,
        current_applied_settings=_applied(limit=20),
        next_applied_settings=_applied(limit=90),
    )
    assert first.model_dump() == second.model_dump()


def test_partial_comparison_quality_preserved():
    current = _strategy()
    next_ = _strategy(budget=4000)
    diff = build_strategy_settings_diff(
        current,
        next_,
        current_applied_settings=_applied(),
        next_applied_settings=_applied(),
        comparison_quality="partial",
    )
    assert diff.comparison_quality == "partial"
