"""Resolves familiar-meals planning preference from Profile (Sprint 5.27)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from strategy.context import ProfileContext

PROFILE_FAMILIAR_MEALS_PREFERENCE_APPLIED = "PROFILE_FAMILIAR_MEALS_PREFERENCE_APPLIED"
PROFILE_FAMILIAR_MEALS_PREFERENCE_DISABLED = "PROFILE_FAMILIAR_MEALS_PREFERENCE_DISABLED"

FamiliarMealsSource = Literal[
    "profile", "learned_preference", "default", "inferred"
]


@dataclass(frozen=True)
class EffectiveFamiliarMealsPreference:
    prefer_familiar_meals: bool
    source: FamiliarMealsSource
    profile_value: bool | None = None


def resolve_effective_familiar_meals_preference(
    profile_context: ProfileContext,
    learned_prefer_familiar: bool | None = None,
) -> EffectiveFamiliarMealsPreference:
    """Resolve Profile > Learned > default; Behavior never bypasses acceptance."""
    profile_pref = profile_context.prefer_familiar_meals
    if profile_pref is True:
        return EffectiveFamiliarMealsPreference(
            prefer_familiar_meals=True,
            source="profile",
            profile_value=True,
        )
    if profile_pref is False:
        return EffectiveFamiliarMealsPreference(
            prefer_familiar_meals=False,
            source="profile",
            profile_value=False,
        )
    if learned_prefer_familiar is True:
        return EffectiveFamiliarMealsPreference(
            prefer_familiar_meals=True,
            source="learned_preference",
            profile_value=None,
        )
    return EffectiveFamiliarMealsPreference(
        prefer_familiar_meals=False,
        source="default",
        profile_value=None,
    )


def familiar_meals_reason_codes(effective: EffectiveFamiliarMealsPreference) -> list[str]:
    if effective.profile_value is True:
        return [PROFILE_FAMILIAR_MEALS_PREFERENCE_APPLIED]
    if effective.profile_value is False:
        return [PROFILE_FAMILIAR_MEALS_PREFERENCE_DISABLED]
    return []
