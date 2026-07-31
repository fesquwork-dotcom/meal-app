"""Lifecycle helpers for Behavior Insight transitions (Sprint 5.28)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from behavior.constants import (
    SNOOZE_DURATION_DAYS,
    BehaviorInsightType,
    BehaviorSnoozeDuration,
)
from behavior.records import BehaviorInsightRecord


def behavior_insight_affects_strategy(insight_type: BehaviorInsightType | str) -> bool:
    """Returns True when confirmed insight directly mutates Strategy fields."""
    normalized = (
        insight_type.value if isinstance(insight_type, BehaviorInsightType) else str(insight_type)
    )
    return normalized == BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION.value


def compute_snoozed_until(now: datetime, duration: BehaviorSnoozeDuration) -> datetime:
    days = SNOOZE_DURATION_DAYS[duration]
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return (current.astimezone(timezone.utc) + timedelta(days=days)).replace(microsecond=0)


def profile_preference_remains_after_revoke(insight: BehaviorInsightRecord) -> bool:
    """True when revoke must preserve an already-applied Profile recommendation."""
    return bool(
        insight.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE.value
        and insight.recommendation_applied_at
    )
