"""Privacy-safe aggregation of strategy-scoped events for Learning."""

from __future__ import annotations

from collections.abc import Sequence

from learning.engine import LearningEvidence
from memory.constants import MemoryEventType, ReplacementReasonCode
from memory.records import MemoryEventRecord
from strategy.models import WeeklyStrategy


def _distinct_count(events: Sequence[MemoryEventRecord]) -> int:
    return len({event.meal_id or event.event_key for event in events})


def build_learning_evidence(
    events: Sequence[MemoryEventRecord],
    strategy: WeeklyStrategy,
) -> LearningEvidence:
    """Aggregate events without exposing ids, raw values, or event payloads."""
    replacements = [
        event
        for event in events
        if event.event_type == MemoryEventType.MEAL_REPLACED.value
    ]
    faster = [
        event
        for event in replacements
        if event.reason_code == ReplacementReasonCode.FASTER.value
    ]
    suited = [
        event
        for event in events
        if event.event_type == MemoryEventType.MEAL_SUITED.value
    ]
    cooked = [
        event
        for event in events
        if event.event_type == MemoryEventType.MEAL_COOKED.value
    ]
    return LearningEvidence(
        replacement_count=_distinct_count(replacements),
        planned_meal_count=strategy.days * strategy.meals_per_day,
        faster_replacement_count=_distinct_count(faster),
        suited_meal_count=_distinct_count(suited),
        cooked_meal_count=_distinct_count(cooked),
        decision_prefer_familiar=strategy.prefer_familiar_meals,
        decision_prefer_faster=strategy.prefer_faster_meals,
        shopping_completed=any(
            event.event_type == MemoryEventType.SHOPPING_COMPLETED.value
            for event in events
        ),
        plan_completed=any(
            event.event_type == MemoryEventType.PLAN_COMPLETED.value
            for event in events
        ),
    )
