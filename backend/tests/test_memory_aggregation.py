"""Unit tests for deterministic memory aggregation (pure functions, no I/O)."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

from memory.aggregation import (
    aggregate_avoid_ingredient,
    aggregate_prefer_faster,
    compute_confidence,
)
from memory.records import MemoryEventRecord, PreferenceSignalRecord

NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)


def _event(
    *,
    days_ago: int = 0,
    reason_code: str = "dislike_ingredient",
    target_value: str | None = "гречка",
    target_type: str | None = "ingredient",
    key: str = "k",
) -> MemoryEventRecord:
    created = (NOW - timedelta(days=days_ago)).isoformat()
    return MemoryEventRecord(
        id=f"id-{key}",
        user_id=1,
        event_type="meal_replaced",
        event_key=key,
        strategy_id="s1",
        meal_id="day2_dinner",
        recipe_id="r1",
        reason_code=reason_code,
        target_type=target_type,
        target_value=target_value,
        target_label="Гречка",
        metadata_json=None,
        created_at=created,
    )


def _signal(**overrides) -> PreferenceSignalRecord:
    base = dict(
        id="sig-1",
        user_id=1,
        signal_type="avoid_ingredient",
        target_value="гречка",
        target_label="Гречка",
        status="observed",
        confidence=0.35,
        evidence_count=1,
        first_observed_at=(NOW - timedelta(days=5)).isoformat(),
        last_observed_at=(NOW - timedelta(days=5)).isoformat(),
        created_at=(NOW - timedelta(days=5)).isoformat(),
        updated_at=(NOW - timedelta(days=5)).isoformat(),
        dismissed_at=None,
    )
    base.update(overrides)
    return PreferenceSignalRecord(**base)


def test_confidence_ladder():
    assert compute_confidence(0) == 0.0
    assert compute_confidence(1) == 0.35
    assert compute_confidence(2) == 0.60
    assert compute_confidence(3) == 0.80
    assert compute_confidence(4) == 0.95
    assert compute_confidence(10) == 0.95


def test_one_dislike_is_observed_low_confidence():
    draft = aggregate_avoid_ingredient([_event(key="a")], None, now=NOW, target_value="гречка")
    assert draft is not None
    assert draft.status == "observed"
    assert draft.confidence == 0.35
    assert draft.evidence_count == 1


def test_repeated_dislikes_increase_evidence_and_autoconfirm():
    events = [_event(key=f"e{i}", days_ago=i) for i in range(3)]
    draft = aggregate_avoid_ingredient(events, None, now=NOW, target_value="гречка")
    assert draft.evidence_count == 3
    assert draft.status == "confirmed"
    assert draft.confidence == 0.80


def test_does_not_mutate_input_events():
    events = [_event(key="a"), _event(key="b", days_ago=1)]
    snapshot = copy.deepcopy(events)
    aggregate_avoid_ingredient(events, None, now=NOW, target_value="гречка")
    assert events == snapshot


def test_profile_exclusion_prevents_active_signal():
    draft = aggregate_avoid_ingredient(
        [_event(key="a")],
        None,
        now=NOW,
        target_value="гречка",
        profile_excluded=True,
    )
    assert draft is None


def test_confirmed_signal_remains_confirmed():
    existing = _signal(status="confirmed", confidence=1.0, evidence_count=2)
    events = [_event(key="a"), _event(key="b", days_ago=1)]
    draft = aggregate_avoid_ingredient(events, existing, now=NOW, target_value="гречка")
    assert draft.status == "confirmed"
    assert draft.confidence == 1.0


def test_dismissed_old_evidence_ignored():
    dismissed_at = (NOW - timedelta(days=1)).isoformat()
    existing = _signal(status="dismissed", dismissed_at=dismissed_at)
    old_events = [_event(key="old", days_ago=5)]
    draft = aggregate_avoid_ingredient(old_events, existing, now=NOW, target_value="гречка")
    assert draft is None


def test_new_post_dismiss_evidence_recreates_signal():
    dismissed_at = (NOW - timedelta(days=3)).isoformat()
    existing = _signal(status="dismissed", dismissed_at=dismissed_at)
    events = [
        _event(key="old", days_ago=5),
        _event(key="new", days_ago=1),
    ]
    draft = aggregate_avoid_ingredient(events, existing, now=NOW, target_value="гречка")
    assert draft is not None
    assert draft.status == "observed"
    assert draft.evidence_count == 1


def test_evidence_window_excludes_old_events():
    events = [
        _event(key="old", days_ago=200),
        _event(key="recent", days_ago=2),
    ]
    draft = aggregate_avoid_ingredient(events, None, now=NOW, target_value="гречка")
    assert draft.evidence_count == 1


def test_faster_one_event_observed():
    events = [_event(key="f", reason_code="faster", target_value=None, target_type=None)]
    draft = aggregate_prefer_faster(events, None, now=NOW)
    assert draft is not None
    assert draft.status == "observed"
    assert draft.confidence == 0.35


def test_faster_repeated_events_increase_confidence_without_autoconfirm():
    events = [
        _event(key=f"f{i}", days_ago=i, reason_code="faster", target_value=None, target_type=None)
        for i in range(4)
    ]
    draft = aggregate_prefer_faster(events, None, now=NOW)
    assert draft.evidence_count == 4
    assert draft.status == "observed"
    assert draft.confidence == 0.95


def test_faster_evidence_window_respected():
    events = [
        _event(key="old", days_ago=120, reason_code="faster", target_value=None, target_type=None),
        _event(key="new", days_ago=1, reason_code="faster", target_value=None, target_type=None),
    ]
    draft = aggregate_prefer_faster(events, None, now=NOW)
    assert draft.evidence_count == 1
