"""Tests for behavior context and application (Sprint 5.26)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from behavior.constants import BehaviorInsightStatus, BehaviorInsightType
from behavior.records import BehaviorInsightRecord
from strategy import StrategyBuilder
from strategy.applied_behavior import (
    BEHAVIOR_AVAILABILITY_FRICTION_APPLIED,
    BEHAVIOR_HIGH_REPLACEMENT_RATE_NEEDS_USER_CHOICE,
    BEHAVIOR_RECIPE_PATTERN_NOT_ACTIONABLE,
    BEHAVIOR_REDUNDANT_WITH_HIGHER_PRIORITY,
)
from strategy.behavior_apply import apply_behavior_insights
from strategy.behavior_context import StrategyBehaviorContext, build_strategy_behavior_context
from strategy.context import ProfileContext
from strategy.memory_context import StrategyMemoryContext, build_strategy_memory_context
from memory.constants import ConfirmationSource, SignalStatus, SignalType
from memory.records import PreferenceSignalRecord


def _insight_record(
    *,
    insight_id: str = "insight-1",
    insight_type: str = BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION.value,
    target_key: str | None = "гречка",
    status: str = BehaviorInsightStatus.CONFIRMED.value,
    updated_at: str = "2026-07-01T10:00:00+00:00",
) -> BehaviorInsightRecord:
    return BehaviorInsightRecord(
        id=insight_id,
        user_id=1,
        insight_key=f"{insight_type}:{target_key or ''}",
        insight_type=insight_type,
        target_key=target_key,
        target_label=target_key,
        status=status,
        confidence=1.0,
        evidence_count=2,
        evidence_window_days=90,
        rule_version=1,
        first_seen_at=updated_at,
        last_seen_at=updated_at,
        created_at=updated_at,
        updated_at=updated_at,
        confirmed_at=updated_at if status == BehaviorInsightStatus.CONFIRMED.value else None,
        dismissed_at=None,
        expires_at=None,
    )


def _memory_avoid(target: str) -> StrategyMemoryContext:
    record = PreferenceSignalRecord(
        id="sig-1",
        user_id=1,
        signal_type=SignalType.AVOID_INGREDIENT.value,
        target_value=target,
        target_label=target,
        status=SignalStatus.CONFIRMED.value,
        confidence=1.0,
        evidence_count=2,
        first_observed_at="2026-07-01T10:00:00+00:00",
        last_observed_at="2026-07-01T10:00:00+00:00",
        created_at="2026-07-01T10:00:00+00:00",
        updated_at="2026-07-01T10:00:00+00:00",
        dismissed_at=None,
        confirmation_source=ConfirmationSource.USER.value,
    )
    return build_strategy_memory_context([record])


def test_behavior_context_includes_confirmed_only():
    records = [
        _insight_record(status=BehaviorInsightStatus.CONFIRMED.value),
        _insight_record(
            insight_id="cand",
            status=BehaviorInsightStatus.CANDIDATE.value,
        ),
        _insight_record(
            insight_id="obs",
            status=BehaviorInsightStatus.OBSERVED.value,
        ),
        _insight_record(
            insight_id="dismissed",
            status=BehaviorInsightStatus.DISMISSED.value,
        ),
        _insight_record(
            insight_id="expired",
            status=BehaviorInsightStatus.EXPIRED.value,
        ),
    ]
    context = build_strategy_behavior_context(records)
    assert len(context.insights) == 1
    assert context.ingredient_availability_frictions[0].target_key == "гречка"


def test_behavior_context_stable_order_and_dedup():
    records = [
        _insight_record(insight_id="b", updated_at="2026-07-02T10:00:00+00:00"),
        _insight_record(insight_id="a", updated_at="2026-07-01T10:00:00+00:00"),
        _insight_record(insight_id="dup", target_key="гречка"),
    ]
    context = build_strategy_behavior_context(records)
    assert [item.insight_id for item in context.ingredient_availability_frictions] == ["a"]


def test_availability_applied_to_strategy():
    profile = {"allergies": "нет", "cooktime": "medium"}
    context = build_strategy_behavior_context([_insight_record()])
    result = StrategyBuilder(
        clock=lambda: datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    ).build_with_reasons(profile, StrategyMemoryContext.empty(), context)
    assert len(result.strategy.availability_avoid_products) == 1
    assert BEHAVIOR_AVAILABILITY_FRICTION_APPLIED in result.reason_codes
    assert result.applied_behavior is not None
    assert any(decision.applied for decision in result.applied_behavior.decisions)


def test_profile_exclusion_wins_over_behavior():
    profile = {"allergies": "гречка", "cooktime": "medium"}
    context = build_strategy_behavior_context([_insight_record()])
    result = StrategyBuilder().build_with_reasons(profile, StrategyMemoryContext.empty(), context)
    assert result.strategy.availability_avoid_products == []
    assert result.applied_behavior is not None
    assert result.applied_behavior.decisions[0].reason_code == BEHAVIOR_REDUNDANT_WITH_HIGHER_PRIORITY


def test_memory_avoid_wins_over_behavior():
    profile = {"allergies": "нет", "cooktime": "medium"}
    context = build_strategy_behavior_context([_insight_record()])
    result = StrategyBuilder().build_with_reasons(profile, _memory_avoid("гречка"), context)
    assert result.strategy.availability_avoid_products == []
    assert result.applied_behavior.decisions[0].reason_code == BEHAVIOR_REDUNDANT_WITH_HIGHER_PRIORITY


def test_recipe_replacement_stored_only():
    record = _insight_record(
        insight_type=BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT.value,
        target_key="recipe_day1_dinner",
    )
    context = build_strategy_behavior_context([record])
    result = StrategyBuilder().build_with_reasons({}, StrategyMemoryContext.empty(), context)
    assert result.strategy.availability_avoid_products == []
    assert result.applied_behavior.decisions[0].reason_code == BEHAVIOR_RECIPE_PATTERN_NOT_ACTIONABLE


def test_high_replacement_rate_stored_only():
    record = _insight_record(
        insight_type=BehaviorInsightType.HIGH_REPLACEMENT_RATE.value,
        target_key=None,
    )
    context = build_strategy_behavior_context([record])
    result = StrategyBuilder().build_with_reasons({}, StrategyMemoryContext.empty(), context)
    assert result.applied_behavior.decisions[0].reason_code == (
        BEHAVIOR_HIGH_REPLACEMENT_RATE_NEEDS_USER_CHOICE
    )


def test_empty_behavior_preserves_strategy():
    profile = {"allergies": "нет", "cooktime": "medium"}
    without = StrategyBuilder().build_with_reasons(profile)
    with_empty = StrategyBuilder().build_with_reasons(
        profile, StrategyMemoryContext.empty(), StrategyBehaviorContext.empty()
    )
    assert without.strategy == with_empty.strategy
    assert with_empty.applied_behavior is None


def test_apply_behavior_is_deterministic():
    profile_context = ProfileContext.from_profile({"allergies": "нет"})
    memory_context = StrategyMemoryContext.empty()
    behavior_context = build_strategy_behavior_context([_insight_record()])
    first = apply_behavior_insights(
        profile_context=profile_context,
        memory_context=memory_context,
        behavior_context=behavior_context,
        effective_excluded_products=[],
    )
    second = apply_behavior_insights(
        profile_context=profile_context,
        memory_context=memory_context,
        behavior_context=behavior_context,
        effective_excluded_products=[],
    )
    assert first == second
