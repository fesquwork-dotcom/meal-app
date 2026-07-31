"""Pure merge rules for promoting a confirmed avoid signal into Profile."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cooking_preferences import (
    PREFER_FASTER_PROMOTED_ID,
    CookingPreferences,
    parse_cooking_preferences,
)
from dietary_constraints import (
    SAFETY_KINDS,
    DietaryConstraint,
    DietaryConstraintKind,
    canonical_constraint_value,
    constraints_from_profile,
    new_constraint_id,
    parse_legacy_allergies,
    serialize_legacy_allergies,
)
from shopping.normalization import display_ingredient_name

PromotionOutcome = Literal["promoted", "already_promoted", "already_covered"]


@dataclass(frozen=True)
class PromotionMergeResult:
    outcome: PromotionOutcome
    constraints: list[DietaryConstraint]
    allergies: str
    cooking_preferences: CookingPreferences
    constraint_id: str
    profile_changed: bool


def _display_for_target(canonical_target: str, label: str | None) -> str:
    if label and label.strip():
        return label.strip()
    return display_ingredient_name(canonical_target) or canonical_target


def apply_promotion_merge(
    profile: dict[str, object],
    *,
    canonical_target: str,
    display_label: str | None,
) -> PromotionMergeResult:
    """Merges a confirmed avoid target into profile dietary constraints.

    Safety constraints (allergy, intolerance) are never downgraded. Matching
    legacy items are classified as preference and removed from the legacy list.
    """
    if not canonical_target:
        raise ValueError("canonical_target must not be empty")

    constraints = list(constraints_from_profile(profile))
    legacy_values = parse_legacy_allergies(profile.get("allergies"))
    allergies = (
        profile.get("allergies")
        if isinstance(profile.get("allergies"), str)
        else serialize_legacy_allergies(legacy_values)
    )
    cooking_preferences = parse_cooking_preferences(profile)

    for constraint in constraints:
        if constraint.canonical_value != canonical_target:
            continue
        if constraint.kind.value in SAFETY_KINDS:
            return PromotionMergeResult(
                outcome="already_covered",
                constraints=constraints,
                allergies=allergies if isinstance(allergies, str) else "нет",
                cooking_preferences=cooking_preferences,
                constraint_id=constraint.id,
                profile_changed=False,
            )
        if constraint.kind == DietaryConstraintKind.PREFERENCE:
            return PromotionMergeResult(
                outcome="already_promoted",
                constraints=constraints,
                allergies=allergies if isinstance(allergies, str) else "нет",
                cooking_preferences=cooking_preferences,
                constraint_id=constraint.id,
                profile_changed=False,
            )

    display = _display_for_target(canonical_target, display_label)
    constraint_id = new_constraint_id()
    new_constraint = DietaryConstraint(
        id=constraint_id,
        kind=DietaryConstraintKind.PREFERENCE,
        value=display,
        canonical_value=canonical_target,
        source="memory",
    )

    updated_legacy = legacy_values[:]
    legacy_converted = False
    for legacy_value in legacy_values:
        if canonical_constraint_value(legacy_value) == canonical_target:
            updated_legacy = [item for item in legacy_values if item != legacy_value]
            legacy_converted = True
            break

    updated_constraints = constraints + [new_constraint]
    updated_allergies = serialize_legacy_allergies(updated_legacy)

    return PromotionMergeResult(
        outcome="promoted",
        constraints=updated_constraints,
        allergies=updated_allergies,
        cooking_preferences=cooking_preferences,
        constraint_id=constraint_id,
        profile_changed=True,
    )


def apply_faster_promotion_merge(profile: dict[str, object]) -> PromotionMergeResult:
    """Promotes confirmed faster signal into permanent cooking preference."""
    constraints = list(constraints_from_profile(profile))
    allergies = (
        profile.get("allergies")
        if isinstance(profile.get("allergies"), str)
        else "нет"
    )
    cooking_preferences = parse_cooking_preferences(profile)

    if cooking_preferences.prefer_faster_meals is True:
        return PromotionMergeResult(
            outcome="already_covered",
            constraints=constraints,
            allergies=allergies,
            cooking_preferences=cooking_preferences,
            constraint_id=PREFER_FASTER_PROMOTED_ID,
            profile_changed=False,
        )

    return PromotionMergeResult(
        outcome="promoted",
        constraints=constraints,
        allergies=allergies,
        cooking_preferences=CookingPreferences(prefer_faster_meals=True),
        constraint_id=PREFER_FASTER_PROMOTED_ID,
        profile_changed=True,
    )
