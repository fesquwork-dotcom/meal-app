"""Tests for planning preferences and familiar meals strategy integration (Sprint 5.27)."""

from __future__ import annotations

from datetime import datetime, timezone

from behavior.constants import BehaviorInsightStatus, BehaviorInsightType
from behavior.records import BehaviorInsightRecord
from behavior.recommendation import get_behavior_recommendation_capability
from planning_preferences import parse_planning_preferences, planning_preferences_to_db_json
from strategy import StrategyBuilder
from strategy.behavior_context import StrategyBehaviorContext, build_strategy_behavior_context
from strategy.context import ProfileContext
from strategy.memory_context import StrategyMemoryContext
from strategy.planning_preference import (
    PROFILE_FAMILIAR_MEALS_PREFERENCE_APPLIED,
    resolve_effective_familiar_meals_preference,
)


def test_planning_preferences_tri_state_round_trip():
    for value in (None, True, False):
        profile = parse_planning_preferences(
            {"planning_preferences": {"prefer_familiar_meals": value}}
        )
        assert profile.prefer_familiar_meals is value
        if value is not None:
            assert planning_preferences_to_db_json(
                {"planning_preferences": {"prefer_familiar_meals": value}}
            ) is not None


def test_profile_true_enables_strategy_field():
    profile = {"planning_preferences": {"prefer_familiar_meals": True}}
    result = StrategyBuilder(
        clock=lambda: datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
    ).build_with_reasons(profile)
    assert result.strategy.prefer_familiar_meals is True
    assert result.strategy.strategy_version == 5
    assert PROFILE_FAMILIAR_MEALS_PREFERENCE_APPLIED in result.reason_codes
    assert result.applied_planning_preferences is not None
    assert result.applied_planning_preferences.familiar_meals_source == "profile"


def test_profile_false_or_null_disables_strategy_field():
    for profile in (
        {"planning_preferences": {"prefer_familiar_meals": False}},
        {},
    ):
        result = StrategyBuilder().build_with_reasons(profile)
        assert result.strategy.prefer_familiar_meals is False


def test_confirmed_behavior_alone_does_not_enable_familiar_meals():
    record = BehaviorInsightRecord(
        id="hr-1",
        user_id=1,
        insight_key="high",
        insight_type=BehaviorInsightType.HIGH_REPLACEMENT_RATE.value,
        target_key=None,
        target_label=None,
        status=BehaviorInsightStatus.CONFIRMED.value,
        confidence=1.0,
        evidence_count=5,
        evidence_window_days=90,
        rule_version=1,
        first_seen_at="2026-07-01T10:00:00+00:00",
        last_seen_at="2026-07-01T10:00:00+00:00",
        created_at="2026-07-01T10:00:00+00:00",
        updated_at="2026-07-01T10:00:00+00:00",
        confirmed_at="2026-07-01T10:00:00+00:00",
        dismissed_at=None,
        expires_at=None,
    )
    context = build_strategy_behavior_context([record])
    result = StrategyBuilder().build_with_reasons(
        {}, StrategyMemoryContext.empty(), context
    )
    assert result.strategy.prefer_familiar_meals is False


def test_recommendation_capability():
    assert (
        get_behavior_recommendation_capability(BehaviorInsightType.HIGH_REPLACEMENT_RATE)
        == "can_enable_familiar_meals"
    )
    assert (
        get_behavior_recommendation_capability(BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT)
        == "stored_only"
    )


def test_effective_familiar_resolver():
    ctx = ProfileContext.from_profile({"planning_preferences": {"prefer_familiar_meals": True}})
    effective = resolve_effective_familiar_meals_preference(ctx)
    assert effective.prefer_familiar_meals is True
    assert effective.source == "profile"
