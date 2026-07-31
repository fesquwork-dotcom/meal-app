"""Resolves cooking hard limits and relative faster-meals preference (Sprint 5.22)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from memory.constants import SignalType
from strategy.context import ProfileContext
from strategy.memory_apply import (
    FASTER_DOWNGRADE,
    MEMORY_FASTER_APPLIED,
    MEMORY_IGNORED_PROFILE_PRIORITY,
    MEMORY_REDUNDANT_WITH_PROFILE,
)
from strategy.memory_context import AppliedMemoryDecision, StrategyMemoryContext

PROFILE_FASTER_MEALS_PREFERENCE_APPLIED = "PROFILE_FASTER_MEALS_PREFERENCE_APPLIED"
PROFILE_FASTER_MEALS_DISABLED = "PROFILE_FASTER_MEALS_DISABLED"
MEMORY_FASTER_MEALS_REDUNDANT_WITH_PROFILE = "MEMORY_FASTER_MEALS_REDUNDANT_WITH_PROFILE"

PreferenceSource = Literal[
    "profile", "learned_preference", "memory", "default"
]


@dataclass(frozen=True)
class EffectiveCookingPreference:
    prefer_faster_meals: bool
    source: PreferenceSource
    profile_value: bool | None = None
    memory_signal_applied: bool = False


@dataclass(frozen=True)
class ResolvedCookingBehavior:
    cooking_time_limit: int
    prefer_faster_meals: bool
    preference_source: PreferenceSource
    memory_reason_codes: list[str]
    faster_decision: AppliedMemoryDecision | None


def resolve_effective_faster_preference(
    profile_context: ProfileContext,
    memory_context: StrategyMemoryContext,
    learned_prefer_faster: bool | None = None,
) -> EffectiveCookingPreference:
    profile_pref = profile_context.prefer_faster_meals
    if profile_pref is True:
        return EffectiveCookingPreference(
            prefer_faster_meals=True,
            source="profile",
            profile_value=True,
            memory_signal_applied=False,
        )
    if profile_pref is False:
        return EffectiveCookingPreference(
            prefer_faster_meals=False,
            source="profile",
            profile_value=False,
            memory_signal_applied=False,
        )
    if learned_prefer_faster is True:
        return EffectiveCookingPreference(
            prefer_faster_meals=True,
            source="learned_preference",
            profile_value=None,
            memory_signal_applied=False,
        )
    if memory_context.prefer_faster_meals:
        return EffectiveCookingPreference(
            prefer_faster_meals=True,
            source="memory",
            profile_value=None,
            memory_signal_applied=True,
        )
    return EffectiveCookingPreference(
        prefer_faster_meals=False,
        source="default",
        profile_value=None,
        memory_signal_applied=False,
    )


def resolve_cooking_behavior(
    *,
    profile_context: ProfileContext,
    memory_context: StrategyMemoryContext,
    base_cooking_time_limit: int,
    learned_prefer_faster: bool | None = None,
) -> ResolvedCookingBehavior:
    """Resolves hard limit and faster preference independently.

    Contract:
    - Profile ``prefer_faster_meals=True`` enables preference without lowering limit.
    - Profile ``prefer_faster_meals=False`` disables preference; Memory is ignored.
    - Profile unset + Memory: explicit cooktime keeps limit, enables preference;
      implicit cooktime may downgrade limit one step and enables preference.
    """
    effective = resolve_effective_faster_preference(
        profile_context,
        memory_context,
        learned_prefer_faster,
    )
    memory_reason_codes: list[str] = []
    faster_decision: AppliedMemoryDecision | None = None
    cooking_time_limit = base_cooking_time_limit

    faster_signal = next(
        (
            signal
            for signal in memory_context.signals
            if signal.signal_type == SignalType.PREFER_FASTER_MEALS.value
        ),
        None,
    )

    profile_pref = profile_context.prefer_faster_meals

    if profile_pref is True:
        memory_reason_codes.append(PROFILE_FASTER_MEALS_PREFERENCE_APPLIED)
        if faster_signal is not None:
            faster_decision = AppliedMemoryDecision(
                signal_id=faster_signal.signal_id,
                signal_type=faster_signal.signal_type,
                target_value=None,
                confirmation_source=faster_signal.confirmation_source,
                applied=False,
                reason_code=MEMORY_FASTER_MEALS_REDUNDANT_WITH_PROFILE,
            )
            memory_reason_codes.append(MEMORY_FASTER_MEALS_REDUNDANT_WITH_PROFILE)
    elif profile_pref is False:
        memory_reason_codes.append(PROFILE_FASTER_MEALS_DISABLED)
        if faster_signal is not None:
            faster_decision = AppliedMemoryDecision(
                signal_id=faster_signal.signal_id,
                signal_type=faster_signal.signal_type,
                target_value=None,
                confirmation_source=faster_signal.confirmation_source,
                applied=False,
                reason_code=MEMORY_IGNORED_PROFILE_PRIORITY,
            )
            memory_reason_codes.append(MEMORY_IGNORED_PROFILE_PRIORITY)
    elif learned_prefer_faster is True:
        # Learned is a relative preference only. It never changes the hard
        # cooking-time limit. A matching Memory signal is lower-priority.
        if faster_signal is not None:
            faster_decision = AppliedMemoryDecision(
                signal_id=faster_signal.signal_id,
                signal_type=faster_signal.signal_type,
                target_value=None,
                confirmation_source=faster_signal.confirmation_source,
                applied=False,
                reason_code="LEARNED_PREFERENCE_REDUNDANT_WITH_MEMORY",
            )
            memory_reason_codes.append(
                "LEARNED_PREFERENCE_REDUNDANT_WITH_MEMORY"
            )
    elif faster_signal is not None:
        limit_reduced = False
        if profile_context.cooktime_is_explicit:
            cooking_time_limit = base_cooking_time_limit
        else:
            downgraded = FASTER_DOWNGRADE.get(base_cooking_time_limit, base_cooking_time_limit)
            cooking_time_limit = downgraded
            limit_reduced = downgraded < base_cooking_time_limit

        faster_decision = AppliedMemoryDecision(
            signal_id=faster_signal.signal_id,
            signal_type=faster_signal.signal_type,
            target_value=None,
            confirmation_source=faster_signal.confirmation_source,
            applied=True,
            reason_code=MEMORY_FASTER_APPLIED,
        )
        memory_reason_codes.append(MEMORY_FASTER_APPLIED)
        if not limit_reduced and profile_context.cooktime_is_explicit:
            # Preference applied without hard-limit change.
            pass

    return ResolvedCookingBehavior(
        cooking_time_limit=cooking_time_limit,
        prefer_faster_meals=effective.prefer_faster_meals,
        preference_source=effective.source,
        memory_reason_codes=sorted(set(memory_reason_codes)),
        faster_decision=faster_decision,
    )
