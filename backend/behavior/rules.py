"""Pure deterministic behavior insight rules."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Sequence

from behavior.constants import (
    AVAILABILITY_FRICTION_THRESHOLD,
    BEHAVIOR_WINDOW_DAYS,
    CONFIDENCE_LADDER,
    CONFIDENCE_MAX,
    FREQUENT_RECIPE_THRESHOLD,
    HIGH_REPLACEMENT_MIN_COUNT,
    HIGH_REPLACEMENT_MIN_STRATEGIES,
    HIGH_REPLACEMENT_RATE_THRESHOLD,
    BehaviorInsightStatus,
    BehaviorInsightType,
)
from behavior.models import BehaviorInsightCandidate
from memory.records import MemoryEventRecord

MEAL_REPLACED_EVENT_TYPE = "meal_replaced"
INGREDIENT_UNAVAILABLE_REASON = "ingredient_unavailable"


def _parse_event_time(created_at: str) -> datetime:
    normalized = created_at.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _window_start(now: datetime, window_days: int) -> datetime:
    return now - timedelta(days=window_days)


def _confidence_for_count(count: int) -> float:
    if count <= 0:
        return 0.0
    if count in CONFIDENCE_LADDER:
        return CONFIDENCE_LADDER[count]
    return CONFIDENCE_MAX


def _status_for_threshold(count: int, threshold: int) -> BehaviorInsightStatus:
    if count >= threshold:
        return BehaviorInsightStatus.CANDIDATE
    return BehaviorInsightStatus.OBSERVED


def _valid_recipe_id(recipe_id: str | None) -> bool:
    if recipe_id is None:
        return False
    stripped = recipe_id.strip()
    return bool(stripped)


def _valid_target_key(target_value: str | None) -> bool:
    if target_value is None:
        return False
    stripped = target_value.strip()
    return bool(stripped)


def _filter_replacement_events(
    events: Sequence[MemoryEventRecord],
    *,
    now: datetime,
    window_days: int,
) -> list[MemoryEventRecord]:
    start = _window_start(now, window_days)
    filtered: list[MemoryEventRecord] = []
    for event in events:
        if event.event_type != MEAL_REPLACED_EVENT_TYPE:
            continue
        event_time = _parse_event_time(event.created_at)
        if event_time < start:
            continue
        filtered.append(event)
    return filtered


def _frequent_recipe_replacement_candidates(
    events: Sequence[MemoryEventRecord],
    *,
    now: datetime,
) -> list[BehaviorInsightCandidate]:
    window_events = _filter_replacement_events(
        events, now=now, window_days=BEHAVIOR_WINDOW_DAYS
    )
    by_recipe: dict[str, list[MemoryEventRecord]] = defaultdict(list)
    for event in window_events:
        if not _valid_recipe_id(event.recipe_id):
            continue
        by_recipe[event.recipe_id].append(event)

    candidates: list[BehaviorInsightCandidate] = []
    for recipe_id in sorted(by_recipe.keys()):
        recipe_events = sorted(
            by_recipe[recipe_id],
            key=lambda item: _parse_event_time(item.created_at),
        )
        count = len(recipe_events)
        if count < 1:
            continue
        first_seen = recipe_events[0].created_at
        last_seen = recipe_events[-1].created_at
        candidates.append(
            BehaviorInsightCandidate(
                insight_type=BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT,
                target_key=recipe_id,
                target_label=None,
                status=_status_for_threshold(count, FREQUENT_RECIPE_THRESHOLD),
                confidence=_confidence_for_count(count),
                evidence_count=count,
                evidence_window_days=BEHAVIOR_WINDOW_DAYS,
                first_seen_at=first_seen,
                last_seen_at=last_seen,
            )
        )
    return candidates


def _ingredient_availability_friction_candidates(
    events: Sequence[MemoryEventRecord],
    *,
    now: datetime,
) -> list[BehaviorInsightCandidate]:
    window_events = _filter_replacement_events(
        events, now=now, window_days=BEHAVIOR_WINDOW_DAYS
    )
    by_target: dict[str, list[MemoryEventRecord]] = defaultdict(list)
    for event in window_events:
        if event.reason_code != INGREDIENT_UNAVAILABLE_REASON:
            continue
        if not _valid_target_key(event.target_value):
            continue
        by_target[event.target_value].append(event)

    candidates: list[BehaviorInsightCandidate] = []
    for target_key in sorted(by_target.keys()):
        target_events = sorted(
            by_target[target_key],
            key=lambda item: _parse_event_time(item.created_at),
        )
        count = len(target_events)
        if count < 1:
            continue
        first_seen = target_events[0].created_at
        last_seen = target_events[-1].created_at
        label = target_events[-1].target_label
        if label is not None and not label.strip():
            label = None
        candidates.append(
            BehaviorInsightCandidate(
                insight_type=BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION,
                target_key=target_key,
                target_label=label,
                status=_status_for_threshold(count, AVAILABILITY_FRICTION_THRESHOLD),
                confidence=_confidence_for_count(count),
                evidence_count=count,
                evidence_window_days=BEHAVIOR_WINDOW_DAYS,
                first_seen_at=first_seen,
                last_seen_at=last_seen,
            )
        )
    return candidates


def _high_replacement_rate_candidate(
    events: Sequence[MemoryEventRecord],
    *,
    strategy_count: int | None,
    now: datetime,
) -> BehaviorInsightCandidate | None:
    if strategy_count is None or strategy_count < HIGH_REPLACEMENT_MIN_STRATEGIES:
        return None

    window_events = _filter_replacement_events(
        events, now=now, window_days=BEHAVIOR_WINDOW_DAYS
    )
    replacement_count = len(window_events)
    if replacement_count < HIGH_REPLACEMENT_MIN_COUNT:
        return None

    rate = replacement_count / strategy_count
    if rate < HIGH_REPLACEMENT_RATE_THRESHOLD:
        return None

    sorted_events = sorted(
        window_events, key=lambda item: _parse_event_time(item.created_at)
    )
    return BehaviorInsightCandidate(
        insight_type=BehaviorInsightType.HIGH_REPLACEMENT_RATE,
        target_key=None,
        target_label=None,
        status=BehaviorInsightStatus.CANDIDATE,
        confidence=_confidence_for_count(replacement_count),
        evidence_count=replacement_count,
        evidence_window_days=BEHAVIOR_WINDOW_DAYS,
        first_seen_at=sorted_events[0].created_at,
        last_seen_at=sorted_events[-1].created_at,
    )


def evaluate_behavior_insights(
    events: Sequence[MemoryEventRecord],
    *,
    strategy_count: int | None,
    now: datetime,
) -> list[BehaviorInsightCandidate]:
    """Evaluate all behavior rules deterministically without side effects."""
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    candidates: list[BehaviorInsightCandidate] = []
    candidates.extend(_frequent_recipe_replacement_candidates(events, now=now))
    candidates.extend(_ingredient_availability_friction_candidates(events, now=now))
    global_candidate = _high_replacement_rate_candidate(
        events, strategy_count=strategy_count, now=now
    )
    if global_candidate is not None:
        candidates.append(global_candidate)

    return sorted(
        candidates,
        key=lambda item: (
            item.insight_type.value,
            item.target_key or "",
            item.first_seen_at,
        ),
    )
