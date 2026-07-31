"""Unit tests for pure behavior insight rules."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from behavior.constants import (
    BehaviorInsightStatus,
    BehaviorInsightType,
)
from behavior.models import BehaviorInsightCandidate
from behavior.policy import (
    BehaviorProfileContext,
    ConfirmedMemoryAvoidSignal,
    filter_behavior_candidates,
)
from behavior.rules import evaluate_behavior_insights
from memory.records import MemoryEventRecord

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


def _event(
    key: str,
    *,
    recipe_id: str | None = "recipe-a",
    reason_code: str = "generic",
    target_value: str | None = None,
    target_label: str | None = None,
    created_at: str | None = None,
    user_id: int = 42,
) -> MemoryEventRecord:
    return MemoryEventRecord(
        id=f"evt-{key}",
        user_id=user_id,
        event_type="meal_replaced",
        event_key=key,
        strategy_id="s1",
        meal_id="day1_lunch",
        recipe_id=recipe_id,
        reason_code=reason_code,
        target_type="ingredient" if target_value else None,
        target_value=target_value,
        target_label=target_label,
        metadata_json=None,
        created_at=created_at or NOW.isoformat(),
    )


def test_frequent_recipe_ignored_without_recipe_id():
    events = [_event("e1", recipe_id=None)]
    result = evaluate_behavior_insights(events, strategy_count=2, now=NOW)
    assert result == []


def test_frequent_recipe_one_event_observed():
    events = [_event("e1")]
    result = evaluate_behavior_insights(events, strategy_count=2, now=NOW)
    assert len(result) == 1
    insight = result[0]
    assert insight.insight_type == BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT
    assert insight.status == BehaviorInsightStatus.OBSERVED
    assert insight.confidence == 0.35
    assert insight.evidence_count == 1


def test_frequent_recipe_two_events_candidate():
    events = [
        _event("e1", created_at=(NOW - timedelta(days=1)).isoformat()),
        _event("e2", created_at=NOW.isoformat()),
    ]
    result = evaluate_behavior_insights(events, strategy_count=2, now=NOW)
    insight = result[0]
    assert insight.status == BehaviorInsightStatus.CANDIDATE
    assert insight.confidence == 0.60
    assert insight.evidence_count == 2


def test_frequent_recipe_confidence_ladder():
    events = [
        _event(f"e{i}", created_at=(NOW - timedelta(days=i)).isoformat())
        for i in range(4)
    ]
    result = evaluate_behavior_insights(events, strategy_count=2, now=NOW)
    assert result[0].confidence == 0.95

    three = events[:3]
    result_three = evaluate_behavior_insights(three, strategy_count=2, now=NOW)
    assert result_three[0].confidence == 0.80


def test_frequent_recipe_excludes_old_events():
    old = _event("old", created_at=(NOW - timedelta(days=91)).isoformat())
    recent = _event("recent")
    result = evaluate_behavior_insights([old, recent], strategy_count=2, now=NOW)
    assert result[0].evidence_count == 1
    assert result[0].status == BehaviorInsightStatus.OBSERVED


def test_frequent_recipe_distinct_recipe_ids():
    events = [
        _event("e1", recipe_id="recipe-a"),
        _event("e2", recipe_id="recipe-b"),
    ]
    result = evaluate_behavior_insights(events, strategy_count=2, now=NOW)
    assert len(result) == 2
    assert {item.target_key for item in result} == {"recipe-a", "recipe-b"}


def test_frequent_recipe_stable_ordering():
    events = [
        _event("e1", recipe_id="recipe-z"),
        _event("e2", recipe_id="recipe-a"),
    ]
    result = evaluate_behavior_insights(events, strategy_count=2, now=NOW)
    assert [item.target_key for item in result] == ["recipe-a", "recipe-z"]


def test_availability_friction_one_observed_two_candidate():
    one = [
        _event(
            "u1",
            recipe_id="recipe-u1",
            reason_code="ingredient_unavailable",
            target_value="buckwheat",
            target_label="Buckwheat",
        )
    ]
    observed = [
        item
        for item in evaluate_behavior_insights(one, strategy_count=2, now=NOW)
        if item.insight_type == BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION
    ][0]
    assert observed.insight_type == BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION
    assert observed.status == BehaviorInsightStatus.OBSERVED

    two = [
        _event(
            "u1",
            recipe_id="recipe-u1",
            reason_code="ingredient_unavailable",
            target_value="buckwheat",
            created_at=(NOW - timedelta(days=2)).isoformat(),
        ),
        _event(
            "u2",
            recipe_id="recipe-u2",
            reason_code="ingredient_unavailable",
            target_value="buckwheat",
        ),
    ]
    candidate = [
        item
        for item in evaluate_behavior_insights(two, strategy_count=2, now=NOW)
        if item.insight_type == BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION
    ][0]
    assert candidate.status == BehaviorInsightStatus.CANDIDATE


def test_availability_friction_missing_target_ignored():
    events = [
        _event(
            "u1",
            recipe_id="recipe-u1",
            reason_code="ingredient_unavailable",
            target_value=None,
        )
    ]
    friction = [
        item
        for item in evaluate_behavior_insights(events, strategy_count=2, now=NOW)
        if item.insight_type == BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION
    ]
    assert friction == []


def test_availability_friction_profile_exclusion_filtered():
    candidate = BehaviorInsightCandidate(
        insight_type=BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION,
        target_key="buckwheat",
        target_label="Buckwheat",
        status=BehaviorInsightStatus.CANDIDATE,
        confidence=0.6,
        evidence_count=2,
        evidence_window_days=90,
        first_seen_at=NOW.isoformat(),
        last_seen_at=NOW.isoformat(),
    )
    filtered = filter_behavior_candidates(
        [candidate],
        profile_context=BehaviorProfileContext(excluded_canonical_targets=frozenset({"buckwheat"})),
        confirmed_memory_signals=[],
    )
    assert filtered == []


def test_availability_friction_confirmed_memory_filtered():
    candidate = BehaviorInsightCandidate(
        insight_type=BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION,
        target_key="buckwheat",
        target_label="Buckwheat",
        status=BehaviorInsightStatus.CANDIDATE,
        confidence=0.6,
        evidence_count=2,
        evidence_window_days=90,
        first_seen_at=NOW.isoformat(),
        last_seen_at=NOW.isoformat(),
    )
    filtered = filter_behavior_candidates(
        [candidate],
        profile_context=BehaviorProfileContext(excluded_canonical_targets=frozenset()),
        confirmed_memory_signals=[ConfirmedMemoryAvoidSignal(target_value="buckwheat")],
    )
    assert filtered == []


def test_high_replacement_rate_below_count_threshold():
    events = [_event(f"e{i}", recipe_id=f"recipe-{i}") for i in range(4)]
    global_rows = [
        item
        for item in evaluate_behavior_insights(events, strategy_count=2, now=NOW)
        if item.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE
    ]
    assert global_rows == []


def test_high_replacement_rate_below_strategy_threshold():
    events = [_event(f"e{i}", recipe_id=f"recipe-{i}") for i in range(6)]
    global_rows = [
        item
        for item in evaluate_behavior_insights(events, strategy_count=1, now=NOW)
        if item.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE
    ]
    assert global_rows == []


def test_high_replacement_rate_below_rate_threshold():
    events = [_event(f"e{i}", recipe_id=f"recipe-{i}") for i in range(5)]
    global_rows = [
        item
        for item in evaluate_behavior_insights(events, strategy_count=3, now=NOW)
        if item.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE
    ]
    assert global_rows == []


def test_high_replacement_rate_exact_threshold():
    events = [_event(f"e{i}", recipe_id=f"recipe-{i}") for i in range(5)]
    result = evaluate_behavior_insights(events, strategy_count=2, now=NOW)
    global_insight = [
        item for item in result if item.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE
    ]
    assert len(global_insight) == 1
    assert global_insight[0].status == BehaviorInsightStatus.CANDIDATE
    assert global_insight[0].target_key is None
    assert global_insight[0].evidence_count == 5


def test_high_replacement_rate_zero_denominator():
    events = [_event(f"e{i}", recipe_id=f"recipe-{i}") for i in range(10)]
    global_rows = [
        item
        for item in evaluate_behavior_insights(events, strategy_count=0, now=NOW)
        if item.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE
    ]
    assert global_rows == []
    global_rows_none = [
        item
        for item in evaluate_behavior_insights(events, strategy_count=None, now=NOW)
        if item.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE
    ]
    assert global_rows_none == []


def test_high_replacement_rate_window_respected():
    old = _event("old", recipe_id="recipe-old", created_at=(NOW - timedelta(days=100)).isoformat())
    recent = [_event(f"r{i}", recipe_id=f"recipe-r{i}") for i in range(4)]
    global_rows = [
        item
        for item in evaluate_behavior_insights([old, *recent], strategy_count=2, now=NOW)
        if item.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE
    ]
    assert global_rows == []
