"""Profile validation for explicit persistence and generation gates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from cooking_preferences import cooking_preferences_dict, parse_cooking_preferences
from planning_preferences import planning_preferences_dict, parse_planning_preferences
from dietary_constraints import (
    KIND_PRIORITY,
    MAX_DIETARY_CONSTRAINTS,
    SAFETY_KINDS,
    canonical_constraint_value,
    constraints_from_profile,
    parse_legacy_allergies,
)
from meal_types import resolve_meal_types
from profile_limits import (
    PROFILE_BUDGET_MAX,
    PROFILE_BUDGET_MIN,
    PROFILE_DAYS_MAX,
    PROFILE_DAYS_MIN,
)
from shopping.normalization import canonical_ingredient_name
from strategy.memory_apply import PROTEIN_CANONICAL_KEYS
from strategy.models import VALID_GOALS, VALID_PROTEINS

ProfileValidationStatus = Literal["valid", "incomplete", "invalid"]


@dataclass(frozen=True)
class ProfileValidationResult:
    status: ProfileValidationStatus
    code: str | None = None
    message: str | None = None
    field: str | None = None


def _normalize_proteins(raw: object) -> tuple[list[str], bool]:
    if not isinstance(raw, list):
        return [], False
    proteins: list[str] = []
    for item in raw:
        if isinstance(item, str):
            protein = item.strip().lower()
            if protein in VALID_PROTEINS and protein not in proteins:
                proteins.append(protein)
    return proteins, True


def _protein_conflicts_with_exclusion(protein: str, exclusion_canonical: str) -> bool:
    if protein == "any":
        return False
    mapped = PROTEIN_CANONICAL_KEYS.get(protein)
    if mapped and canonical_ingredient_name(mapped) == exclusion_canonical:
        return True
    return canonical_ingredient_name(protein) == exclusion_canonical


def _profile_exclusions_canonical(profile: dict[str, object]) -> set[str]:
    """All exclusion canonicals: typed constraints plus legacy raw allergies."""
    canonicals: set[str] = set()
    for constraint in constraints_from_profile(profile):
        canonicals.add(constraint.canonical_value)
    for legacy_value in parse_legacy_allergies(profile.get("allergies")):
        canonicals.add(canonical_constraint_value(legacy_value))
    canonicals.discard("")
    return canonicals


def _validate_dietary_constraints(profile: dict[str, object]) -> ProfileValidationResult | None:
    constraints = constraints_from_profile(profile)
    if len(constraints) > MAX_DIETARY_CONSTRAINTS:
        return ProfileValidationResult(
            status="invalid",
            code="PROFILE_TOO_MANY_CONSTRAINTS",
            message="Too many dietary constraints",
            field="dietary_constraints",
        )

    seen: dict[str, str] = {}
    for constraint in constraints:
        if not constraint.value.strip() or not constraint.canonical_value.strip():
            return ProfileValidationResult(
                status="invalid",
                code="PROFILE_CONSTRAINT_VALUE_EMPTY",
                message="Constraint value must not be empty",
                field="dietary_constraints",
            )
        previous_kind = seen.get(constraint.canonical_value)
        if previous_kind is not None:
            # Same-canonical duplicates must already be merged safety-first.
            return ProfileValidationResult(
                status="invalid",
                code="PROFILE_CONSTRAINT_DUPLICATE",
                message="Duplicate dietary constraint",
                field="dietary_constraints",
            )
        seen[constraint.canonical_value] = constraint.kind.value
    return None


def validate_profile_payload(profile: dict[str, object]) -> ProfileValidationResult:
    """Validates profile for explicit save (rejects invalid, allows incomplete)."""
    raw_goal = profile.get("goal")
    goal = raw_goal.strip().lower() if isinstance(raw_goal, str) else ""
    if goal not in VALID_GOALS:
        return ProfileValidationResult(
            status="invalid",
            code="PROFILE_INVALID",
            message="Invalid goal",
            field="goal",
        )

    raw_days = profile.get("days")
    if (
        not isinstance(raw_days, int)
        or isinstance(raw_days, bool)
        or raw_days < PROFILE_DAYS_MIN
        or raw_days > PROFILE_DAYS_MAX
    ):
        return ProfileValidationResult(
            status="invalid", code="PROFILE_INVALID", message="Invalid days", field="days"
        )

    raw_budget = profile.get("budget")
    if (
        not isinstance(raw_budget, (int, float))
        or isinstance(raw_budget, bool)
        or raw_budget < PROFILE_BUDGET_MIN
        or raw_budget > PROFILE_BUDGET_MAX
    ):
        return ProfileValidationResult(
            status="invalid",
            code="PROFILE_INVALID",
            message="Invalid budget",
            field="budget",
        )

    meal_types = resolve_meal_types(
        profile.get("meal_types") if isinstance(profile.get("meal_types"), list) else None,
        profile.get("meals_per_day") if isinstance(profile.get("meals_per_day"), int) else None,
    )
    if not meal_types:
        return ProfileValidationResult(
            status="incomplete",
            code="PROFILE_INCOMPLETE",
            message="Meal types are required",
            field="meal_types",
        )

    constraint_result = _validate_dietary_constraints(profile)
    if constraint_result is not None:
        return constraint_result

    proteins, proteins_present = _normalize_proteins(profile.get("proteins"))
    if proteins_present:
        if not proteins:
            return ProfileValidationResult(
                status="incomplete",
                code="PROFILE_PROTEIN_REQUIRED",
                message="Protein selection is required",
                field="proteins",
            )
        if "any" in proteins and len(proteins) > 1:
            return ProfileValidationResult(
                status="invalid",
                code="PROFILE_ANY_WITH_SPECIFIC_PROTEINS",
                message="Any proteins cannot be combined with specific proteins",
                field="proteins",
            )

    exclusions = _profile_exclusions_canonical(profile)
    for protein in proteins:
        if protein != "any" and any(
            _protein_conflicts_with_exclusion(protein, exclusion) for exclusion in exclusions
        ):
            return ProfileValidationResult(
                status="invalid",
                code="PROFILE_PROTEIN_EXCLUDED",
                message="Preferred protein conflicts with profile exclusions",
                field="proteins",
            )

    return ProfileValidationResult(status="valid")


def _sorted_constraint_dicts(profile: dict[str, object]) -> list[dict[str, object]]:
    constraints = constraints_from_profile(profile)
    ordered = sorted(
        constraints,
        key=lambda item: (KIND_PRIORITY.get(item.kind.value, 99), item.canonical_value),
    )
    return [constraint.model_dump(mode="json") for constraint in ordered]


def normalize_profile_for_persistence(profile: dict[str, object]) -> dict[str, object]:
    """Returns normalized profile dict safe for persistence and hash comparison."""
    meal_types = resolve_meal_types(
        profile.get("meal_types") if isinstance(profile.get("meal_types"), list) else None,
        profile.get("meals_per_day") if isinstance(profile.get("meals_per_day"), int) else None,
    )
    proteins, proteins_present = _normalize_proteins(profile.get("proteins"))

    raw_allergies = profile.get("allergies")
    allergies = raw_allergies.strip() if isinstance(raw_allergies, str) else "нет"
    if not allergies:
        allergies = "нет"

    raw_goal = profile.get("goal")
    goal = raw_goal.strip().lower() if isinstance(raw_goal, str) else "home"

    raw_cooktime = profile.get("cooktime")
    cooktime = raw_cooktime.strip().lower() if isinstance(raw_cooktime, str) else "medium"

    raw_store = profile.get("store")
    store = raw_store.strip() if isinstance(raw_store, str) else "any"

    cooking_raw = profile.get("cooking_preferences")
    if cooking_raw is not None and isinstance(cooking_raw, dict):
        cooking_preferences = cooking_preferences_dict(
            parse_cooking_preferences(profile),
            present=True,
        )
    else:
        cooking_preferences = None

    planning_raw = profile.get("planning_preferences")
    if planning_raw is not None and isinstance(planning_raw, dict):
        planning_preferences = planning_preferences_dict(
            parse_planning_preferences(profile),
            present=True,
        )
    else:
        planning_preferences = None

    return {
        "first_name": str(profile.get("first_name") or "").strip(),
        "days": profile.get("days"),
        "budget": profile.get("budget"),
        "meal_types": meal_types,
        "meals_per_day": len(meal_types),
        "persons": profile.get("persons"),
        "proteins": proteins,
        "goal": goal,
        "cooktime": cooktime,
        "allergies": allergies,
        "dietary_constraints": _sorted_constraint_dicts(profile),
        "cooking_preferences": cooking_preferences,
        "planning_preferences": planning_preferences,
        "store": store,
    }


def profile_has_safety_constraints(profile: dict[str, object]) -> bool:
    return any(
        constraint.kind.value in SAFETY_KINDS
        for constraint in constraints_from_profile(profile)
    )


def validate_profile_for_generation(profile: dict[str, object]) -> ProfileValidationResult:
    result = validate_profile_payload(profile)
    if result.status != "valid":
        return result
    proteins, proteins_present = _normalize_proteins(profile.get("proteins"))
    if proteins_present and not proteins:
        return ProfileValidationResult(
            status="incomplete",
            code="PROFILE_PROTEIN_REQUIRED",
            message="Protein selection is required before generation",
            field="proteins",
        )
    return ProfileValidationResult(status="valid")
