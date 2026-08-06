"""Unit tests for deterministic strategy explanation engine."""

from __future__ import annotations

import pytest

from strategy.builder import StrategyBuilder
from strategy.explanation import (
    EXPLANATION_VERSION,
    build_strategy_explanation,
)
from strategy.models import WeeklyStrategy
from strategy.reason_codes import collect_reason_codes, infer_reason_codes
from strategy.context import ProfileContext
from tests.strategy_fixtures import build_test_profile


def _build_strategy(**profile_overrides: object) -> WeeklyStrategy:
    return StrategyBuilder().build(build_test_profile(**profile_overrides))


def test_same_strategy_produces_same_explanation():
    strategy = _build_strategy(goal="budget", days=7, cooktime="medium")
    first = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    second = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))

    assert first.model_dump() == second.model_dump()


def test_build_strategy_explanation_does_not_mutate_strategy():
    strategy = _build_strategy()
    snapshot = strategy.model_dump()
    build_strategy_explanation(strategy)
    assert strategy.model_dump() == snapshot


def test_cook_days_reduced_explained():
    strategy = _build_strategy(goal="budget", days=7, cooktime="medium")
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))

    cook_reason = next(
        (reason for reason in explanation.reasons if reason.code == "COOK_DAYS_REDUCE_DAILY_WORK"),
        None,
    )
    assert cook_reason is not None
    assert "дни" in cook_reason.description.lower()


def test_daily_cooking_explained():
    strategy = _build_strategy(goal="restaurant", days=7, cooktime="slow")
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))

    daily_reason = next(
        (
            reason
            for reason in explanation.reasons
            if reason.code
            in {"COOK_DAYS_DAILY_VARIETY", "COOK_DAYS_DAILY_NO_LEFTOVERS"}
        ),
        None,
    )
    assert daily_reason is not None
    desc = daily_reason.description.lower()
    assert "каждый день" in desc or "каждому дню" in desc


def test_leftovers_enabled_explained():
    strategy = _build_strategy(goal="home")
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    codes = {reason.code for reason in explanation.reasons}
    if strategy.leftovers_enabled:
        assert "LEFTOVERS_REDUCE_COOKING" in codes
    else:
        assert "LEFTOVERS_REDUCE_COOKING" not in codes


def test_leftovers_disabled_not_claimed():
    strategy = _build_strategy(goal="home")
    strategy = strategy.model_copy(update={"leftovers_enabled": False})
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    codes = {reason.code for reason in explanation.reasons}
    assert "LEFTOVERS_REDUCE_COOKING" not in codes


def test_repeat_flags_explained():
    strategy = _build_strategy(goal="budget", days=5, cooktime="slow")
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    codes = {reason.code for reason in explanation.reasons}
    assert "REPEAT_BREAKFASTS_SAVE_TIME" in codes
    assert "REPEAT_DINNERS_SUPPORT_BUDGET" in codes


def test_single_shopping_day_explained():
    strategy = _build_strategy(days=3)
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    reason = next(
        (item for item in explanation.reasons if item.code == "SHOPPING_DAYS_SINGLE_TRIP"),
        None,
    )
    assert reason is not None
    assert "один раз" in reason.description.lower()


def test_split_shopping_days_explained():
    strategy = _build_strategy(days=7, goal="budget", cooktime="slow")
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    reason = next(
        (
            item
            for item in explanation.reasons
            if item.code == "SHOPPING_DAYS_SPLIT_FRESH_PRODUCTS"
        ),
        None,
    )
    assert reason is not None
    assert "разделена" in reason.description.lower()


def test_fast_cooking_time_explained():
    strategy = _build_strategy(cooktime="fast")
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    reason = next(
        (item for item in explanation.reasons if item.code == "COOKING_TIME_LIMIT_FAST"),
        None,
    )
    assert reason is not None
    assert "20" in reason.description


def test_medium_cooking_time_explained():
    strategy = _build_strategy(cooktime="medium")
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    reason = next(
        (item for item in explanation.reasons if item.code == "COOKING_TIME_LIMIT_MEDIUM"),
        None,
    )
    assert reason is not None
    assert "45" in reason.description


def test_slow_cooking_time_explained():
    strategy = _build_strategy(cooktime="slow")
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    reason = next(
        (item for item in explanation.reasons if item.code == "COOKING_TIME_LIMIT_SLOW"),
        None,
    )
    assert reason is not None
    assert str(strategy.cooking_time_limit) in reason.description


def test_budget_wording_is_approximate():
    strategy = _build_strategy(goal="budget", budget=5000)
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    budget_reason = next(
        (item for item in explanation.reasons if item.code == "BUDGET_LIMITED_VARIETY"),
        None,
    )
    assert budget_reason is not None
    assert "ориентировоч" in budget_reason.description.lower()
    assert "5 000" in budget_reason.description


def test_any_protein_does_not_create_useless_reason():
    strategy = _build_strategy(proteins=["any"])
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    codes = {reason.code for reason in explanation.reasons}
    assert "PROTEIN_ROTATION_FOR_VARIETY" not in codes


def test_exclusions_not_listed_in_summary():
    strategy = _build_strategy(allergies="орехи, молоко")
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    assert "орех" not in explanation.summary.lower()
    assert "молок" not in explanation.summary.lower()


def test_reasons_sorted_by_priority():
    strategy = _build_strategy(goal="budget", days=7)
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    priorities = [reason.priority for reason in explanation.reasons]
    assert priorities == sorted(priorities)


def test_backend_keeps_all_reasons_not_only_ui_limit():
    strategy = _build_strategy(goal="budget", days=7, allergies="глютен")
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    assert len(explanation.reasons) >= 5


def test_unknown_reason_code_handled():
    strategy = _build_strategy()
    explanation = build_strategy_explanation(
        strategy,
        reason_codes=["UNKNOWN_TEST_CODE", "GOAL_HOME"],
    )
    codes = {reason.code for reason in explanation.reasons}
    assert "GOAL_HOME" in codes
    assert "UNKNOWN_TEST_CODE" not in codes


def test_legacy_inferred_explanation_works():
    strategy = _build_strategy(goal="home", days=7)
    explanation = build_strategy_explanation(strategy, source="inferred")
    assert explanation.source == "inferred"
    assert explanation.headline
    assert explanation.summary
    assert explanation.reasons


def test_recorded_explanation_uses_source():
    strategy = _build_strategy(goal="home")
    context = ProfileContext.from_profile(build_test_profile())
    codes = collect_reason_codes(context, strategy)
    explanation = build_strategy_explanation(strategy, reason_codes=codes, source="recorded")
    assert explanation.source == "recorded"
    assert explanation.version == EXPLANATION_VERSION


def test_headline_does_not_contain_raw_enums():
    strategy = _build_strategy(goal="budget", days=7)
    explanation = build_strategy_explanation(strategy, reason_codes=infer_reason_codes(strategy))
    assert "repeat_breakfasts" not in explanation.headline
    assert "cook_days" not in explanation.headline


def test_memory_avoid_reason_explained_without_targets():
    strategy = _build_strategy(allergies="гречка")
    explanation = build_strategy_explanation(
        strategy,
        reason_codes=["MEMORY_AVOID_INGREDIENT_APPLIED", "GOAL_HOME"],
    )
    memory_reason = next(
        (reason for reason in explanation.reasons if reason.code == "MEMORY_AVOID_INGREDIENT_APPLIED"),
        None,
    )
    assert memory_reason is not None
    assert "гречка" not in memory_reason.description.lower()
    assert "подтвержд" in memory_reason.description.lower()


def test_memory_faster_reason_explained():
    strategy = _build_strategy(cooktime="medium")
    explanation = build_strategy_explanation(
        strategy,
        reason_codes=["MEMORY_FASTER_MEALS_APPLIED", "GOAL_HOME"],
    )
    faster_reason = next(
        (reason for reason in explanation.reasons if reason.code == "MEMORY_FASTER_MEALS_APPLIED"),
        None,
    )
    assert faster_reason is not None
    assert "быстр" in faster_reason.description.lower()
