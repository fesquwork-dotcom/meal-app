"""Stable enums and limits for the Behavior Learning Engine (Sprint 5.25A)."""

from __future__ import annotations

from enum import StrEnum

BEHAVIOR_RULES_VERSION = 1

BEHAVIOR_WINDOW_DAYS = 90
FREQUENT_RECIPE_THRESHOLD = 2
AVAILABILITY_FRICTION_THRESHOLD = 2
HIGH_REPLACEMENT_MIN_COUNT = 5
HIGH_REPLACEMENT_MIN_STRATEGIES = 2
HIGH_REPLACEMENT_RATE_THRESHOLD = 2.0
BEHAVIOR_INSIGHT_TTL_DAYS = 180

CONFIDENCE_LADDER: dict[int, float] = {1: 0.35, 2: 0.60, 3: 0.80}
CONFIDENCE_MAX = 0.95
CONFIDENCE_CONFIRMED = 1.0

MAX_EVENTS_PER_EVALUATION = 500


class BehaviorInsightType(StrEnum):
    FREQUENT_RECIPE_REPLACEMENT = "frequent_recipe_replacement"
    INGREDIENT_AVAILABILITY_FRICTION = "ingredient_availability_friction"
    HIGH_REPLACEMENT_RATE = "high_replacement_rate"


class BehaviorInsightStatus(StrEnum):
    OBSERVED = "observed"
    CANDIDATE = "candidate"
    SNOOZED = "snoozed"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    REVOKED = "revoked"
    EXPIRED = "expired"


class BehaviorSnoozeDuration(StrEnum):
    SEVEN_DAYS = "7_days"
    THIRTY_DAYS = "30_days"


SNOOZE_DURATION_DAYS: dict[BehaviorSnoozeDuration, int] = {
    BehaviorSnoozeDuration.SEVEN_DAYS: 7,
    BehaviorSnoozeDuration.THIRTY_DAYS: 30,
}


ACTIVE_BEHAVIOR_STATUSES: frozenset[str] = frozenset(
    {
        BehaviorInsightStatus.OBSERVED.value,
        BehaviorInsightStatus.CANDIDATE.value,
        BehaviorInsightStatus.SNOOZED.value,
        BehaviorInsightStatus.CONFIRMED.value,
    }
)
