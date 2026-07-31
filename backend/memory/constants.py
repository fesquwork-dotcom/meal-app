"""Stable enums and limits for the Memory Engine.

Machine codes are the contract — never rely on user-facing display text.
"""

from __future__ import annotations

from enum import StrEnum


class MemoryEventType(StrEnum):
    """Structured user actions recorded as durable events."""

    MEAL_REPLACED = "meal_replaced"
    # Sprint 6.5 — explicit positive outcome events. They are recorded as
    # evidence only and never feed preference signals or the Decision Engine.
    MEAL_COOKED = "meal_cooked"
    MEAL_SUITED = "meal_suited"
    SHOPPING_COMPLETED = "shopping_completed"
    PLAN_COMPLETED = "plan_completed"
    # Reserved for future sprints once a reliable user action exists.
    MEAL_KEPT = "meal_kept"
    RECIPE_OPENED = "recipe_opened"
    RECIPE_COMPLETED = "recipe_completed"


# Positive events accepted from the client. Meal-scoped events require a
# meal_id; strategy-scoped events are recorded at most once per strategy.
MEAL_SCOPED_POSITIVE_EVENT_TYPES: frozenset[str] = frozenset(
    {MemoryEventType.MEAL_COOKED.value, MemoryEventType.MEAL_SUITED.value}
)
STRATEGY_SCOPED_POSITIVE_EVENT_TYPES: frozenset[str] = frozenset(
    {
        MemoryEventType.SHOPPING_COMPLETED.value,
        MemoryEventType.PLAN_COMPLETED.value,
    }
)
POSITIVE_EVENT_TYPES: frozenset[str] = (
    MEAL_SCOPED_POSITIVE_EVENT_TYPES | STRATEGY_SCOPED_POSITIVE_EVENT_TYPES
)


class ReplacementReasonCode(StrEnum):
    GENERIC = "generic"
    FASTER = "faster"
    DISLIKE_INGREDIENT = "dislike_ingredient"
    INGREDIENT_UNAVAILABLE = "ingredient_unavailable"
    OTHER = "other"


class SignalType(StrEnum):
    AVOID_INGREDIENT = "avoid_ingredient"
    PREFER_FASTER_MEALS = "prefer_faster_meals"
    # Defined but not auto-promoted to a permanent preference this sprint.
    INGREDIENT_AVAILABILITY_ISSUE = "ingredient_availability_issue"
    FREQUENTLY_REPLACED_RECIPE = "frequently_replaced_recipe"


class SignalStatus(StrEnum):
    OBSERVED = "observed"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class ConfirmationSource(StrEnum):
    USER = "user"
    AUTOMATIC = "automatic"


class TargetType(StrEnum):
    INGREDIENT = "ingredient"


ACTIVE_SIGNAL_STATUSES: frozenset[str] = frozenset(
    {SignalStatus.OBSERVED.value, SignalStatus.CONFIRMED.value}
)

VALID_REASON_CODES: frozenset[str] = frozenset(code.value for code in ReplacementReasonCode)

# Aggregation contract
EVIDENCE_WINDOW_DAYS = 90
AVOID_AUTO_CONFIRM_MIN_EVIDENCE = 3
CONFIDENCE_LADDER: dict[int, float] = {1: 0.35, 2: 0.60, 3: 0.80}
CONFIDENCE_MAX = 0.95
CONFIDENCE_CONFIRMED = 1.0

# Security limits
MAX_TARGET_LENGTH = 80
MAX_EVENT_KEY_LENGTH = 100
MAX_MEAL_ID_LENGTH = 100
MAX_EVENTS_PER_AGGREGATION = 500
MAX_SIGNALS_RETURNED = 100
