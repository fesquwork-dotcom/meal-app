"""Deterministic field resolvers for WeeklyStrategy construction."""

from __future__ import annotations

from datetime import datetime, timezone

from strategy.context import ProfileContext
from strategy.effective_exclusions import build_profile_exclusions
from strategy.models import DEFAULT_COOKING_TIME_LIMIT

COOKTIME_LIMITS_MINUTES: dict[str, int] = {
    "fast": 20,
    "medium": 45,
    "slow": 90,
}

LEFTOVERS_GOALS = frozenset({"home", "healthy", "budget", "weightloss"})
BATCH_COOK_GOALS = frozenset({"home", "budget", "muscle"})


def resolve_goal(context: ProfileContext) -> str:
    return context.goal


def resolve_days(context: ProfileContext) -> int:
    return context.days


def resolve_budget(context: ProfileContext) -> float:
    return context.budget


def resolve_meal_types_list(context: ProfileContext) -> list[str]:
    return list(context.meal_types)


def resolve_meals_per_day(context: ProfileContext) -> int:
    return len(context.meal_types)


def resolve_cook_days(
    context: ProfileContext,
    *,
    leftovers_enabled: bool | None = None,
) -> list[int]:
    """Resolve preferred cook days with leftovers consistency (Sprint 10.11.6).

    When leftovers are disabled, non-cook days cannot be closed by leftover
    coverage, so cook days must cover the full planning horizon.
    """
    leftovers = (
        resolve_leftovers_enabled(context)
        if leftovers_enabled is None
        else bool(leftovers_enabled)
    )
    all_days = list(range(1, context.days + 1))

    # Consistency: leftovers=false → daily cook days (do not enable leftovers).
    if not leftovers:
        return all_days

    if context.days <= 3 or context.cooktime == "fast":
        return all_days

    if context.goal in BATCH_COOK_GOALS:
        return sorted({1, 3, 5, 7, context.days} & set(range(1, context.days + 1)))

    return all_days


def resolve_shopping_days(context: ProfileContext) -> list[int]:
    if context.days <= 1:
        return [1]

    midpoint = max(1, (context.days + 1) // 2)
    if context.goal == "budget" and context.days >= 5:
        return [1, midpoint]

    return [1]


def resolve_leftovers_enabled(context: ProfileContext) -> bool:
    return context.goal in LEFTOVERS_GOALS


def resolve_repeat_breakfasts(context: ProfileContext) -> bool:
    return context.goal == "budget"


def resolve_repeat_lunches(context: ProfileContext) -> bool:
    return context.goal in {"budget", "muscle"}


def resolve_repeat_dinners(context: ProfileContext) -> bool:
    return context.goal == "budget" and context.days >= 5


def resolve_preferred_proteins(context: ProfileContext) -> list[str]:
    return list(context.proteins)


def resolve_excluded_products(context: ProfileContext) -> list[str]:
    """Display values of all profile-side effective exclusions.

    Ordered by source priority (allergy, intolerance, legacy, preference)
    with canonical deduplication handled by the effective exclusion model.
    """
    return [item.display_value for item in build_profile_exclusions(context)]


def resolve_cooking_time_limit(context: ProfileContext) -> int:
    return COOKTIME_LIMITS_MINUTES.get(context.cooktime, DEFAULT_COOKING_TIME_LIMIT)


def resolve_generated_at(_context: ProfileContext, *, now: datetime | None = None) -> str:
    timestamp = now or datetime.now(timezone.utc)
    return timestamp.replace(microsecond=0).isoformat()
