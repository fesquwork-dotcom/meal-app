"""Policy filtering for behavior insight candidates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from behavior.constants import BehaviorInsightType
from behavior.models import BehaviorInsightCandidate


@dataclass(frozen=True)
class BehaviorProfileContext:
    """Minimal profile exclusion context for policy filtering."""

    excluded_canonical_targets: frozenset[str]


@dataclass(frozen=True)
class ConfirmedMemoryAvoidSignal:
    """Confirmed avoid_ingredient memory signal used for overlap checks."""

    target_value: str


def filter_behavior_candidates(
    candidates: Sequence[BehaviorInsightCandidate],
    *,
    profile_context: BehaviorProfileContext,
    confirmed_memory_signals: Sequence[ConfirmedMemoryAvoidSignal],
) -> list[BehaviorInsightCandidate]:
    """Drop candidates that duplicate Profile or confirmed Memory state."""
    memory_avoids = frozenset(
        signal.target_value for signal in confirmed_memory_signals
    )
    filtered: list[BehaviorInsightCandidate] = []
    for candidate in candidates:
        if candidate.insight_type != BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION:
            filtered.append(candidate)
            continue
        target = candidate.target_key
        if target is None:
            continue
        if target in profile_context.excluded_canonical_targets:
            continue
        if target in memory_avoids:
            continue
        filtered.append(candidate)
    return filtered
