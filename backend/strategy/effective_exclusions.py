"""Effective exclusion model: unified view over profile constraints and legacy
allergies (Sprint 5.20). Memory avoids are merged later by memory_apply."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from dietary_constraints import (
    DietaryConstraintKind,
    canonical_constraint_value,
    parse_legacy_allergies,
)
from strategy.context import ProfileContext

ExclusionSource = Literal[
    "profile_allergy",
    "profile_intolerance",
    "profile_preference",
    "profile_legacy",
    "memory",
]

# Lower number = higher priority; safety sources always win merges.
SOURCE_PRIORITY: dict[str, int] = {
    "profile_allergy": 0,
    "profile_intolerance": 1,
    "profile_legacy": 2,
    "profile_preference": 3,
    "memory": 4,
}

SAFETY_SOURCES = frozenset({"profile_allergy", "profile_intolerance", "profile_legacy"})

_KIND_TO_SOURCE: dict[str, ExclusionSource] = {
    DietaryConstraintKind.ALLERGY.value: "profile_allergy",
    DietaryConstraintKind.INTOLERANCE.value: "profile_intolerance",
    DietaryConstraintKind.PREFERENCE.value: "profile_preference",
}


@dataclass(frozen=True)
class EffectiveExclusion:
    canonical_value: str
    display_value: str
    source: ExclusionSource
    removable_in_conflict: bool


def build_profile_exclusions(context: ProfileContext) -> list[EffectiveExclusion]:
    """Builds deduplicated profile-side exclusions with safety-first merge.

    Sources in priority order: allergy, intolerance, legacy unspecified,
    explicit profile preference. Unclassified legacy values behave as safety
    constraints (hard exclusion, never removable through conflict resolution)
    without being labeled as allergies.
    """
    best: dict[str, EffectiveExclusion] = {}

    def _offer(exclusion: EffectiveExclusion) -> None:
        current = best.get(exclusion.canonical_value)
        if current is None or (
            SOURCE_PRIORITY[exclusion.source] < SOURCE_PRIORITY[current.source]
        ):
            best[exclusion.canonical_value] = exclusion

    for constraint in context.dietary_constraints:
        source = _KIND_TO_SOURCE.get(constraint.kind.value)
        if source is None:
            continue
        canonical = constraint.canonical_value or canonical_constraint_value(constraint.value)
        if not canonical:
            continue
        _offer(
            EffectiveExclusion(
                canonical_value=canonical,
                display_value=constraint.value,
                source=source,
                removable_in_conflict=source == "profile_preference",
            )
        )

    for legacy_value in parse_legacy_allergies(context.allergies):
        canonical = canonical_constraint_value(legacy_value)
        if not canonical:
            continue
        _offer(
            EffectiveExclusion(
                canonical_value=canonical,
                display_value=legacy_value,
                source="profile_legacy",
                removable_in_conflict=False,
            )
        )

    return sorted(
        best.values(),
        key=lambda item: (SOURCE_PRIORITY[item.source], item.canonical_value),
    )


def exclusion_by_canonical(
    exclusions: list[EffectiveExclusion], canonical: str
) -> EffectiveExclusion | None:
    for exclusion in exclusions:
        if exclusion.canonical_value == canonical:
            return exclusion
    return None


def has_legacy_exclusions(context: ProfileContext) -> bool:
    return bool(parse_legacy_allergies(context.allergies))
