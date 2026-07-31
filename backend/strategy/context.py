"""Normalized profile view consumed by strategy resolvers."""

from __future__ import annotations

from dataclasses import dataclass, field

from planning_preferences import parse_planning_preferences
from cooking_preferences import parse_cooking_preferences
from dietary_constraints import (
    DietaryConstraint,
    DietaryConstraintKind,
    canonical_constraint_value,
    constraints_from_profile,
    parse_legacy_allergies,
    serialize_legacy_allergies,
)
from meal_types import resolve_meal_types
from profile_limits import clamp_legacy_budget, clamp_legacy_days
from strategy.models import DEFAULT_BUDGET, DEFAULT_DAYS, DEFAULT_GOAL, VALID_GOALS, VALID_PROTEINS


@dataclass(frozen=True)
class ProfileContext:
    """Immutable, normalized profile snapshot for deterministic strategy building."""

    goal: str
    days: int
    budget: float
    meals_per_day: int
    meal_types: list[str]
    proteins: list[str]
    cooktime: str
    allergies: str
    cooktime_is_explicit: bool = False
    proteins_explicit: bool = False
    prefer_faster_meals: bool | None = None
    prefer_familiar_meals: bool | None = None
    dietary_constraints: tuple[DietaryConstraint, ...] = field(default_factory=tuple)

    @classmethod
    def from_profile(cls, profile: dict[str, object] | None) -> "ProfileContext":
        source = profile or {}

        raw_goal = source.get("goal")
        goal = raw_goal.strip().lower() if isinstance(raw_goal, str) else DEFAULT_GOAL
        if goal not in VALID_GOALS:
            goal = DEFAULT_GOAL

        days = clamp_legacy_days(source.get("days"), default=DEFAULT_DAYS)

        budget = clamp_legacy_budget(source.get("budget"), default=DEFAULT_BUDGET)

        raw_meal_types = source.get("meal_types")
        meal_types_list = (
            [item for item in raw_meal_types if isinstance(item, str)]
            if isinstance(raw_meal_types, list)
            else None
        )
        raw_meals_per_day = source.get("meals_per_day")
        meals_per_day_value = (
            raw_meals_per_day
            if isinstance(raw_meals_per_day, int) and not isinstance(raw_meals_per_day, bool)
            else None
        )
        meal_types = resolve_meal_types(meal_types_list, meals_per_day_value)
        meals_per_day = len(meal_types)

        raw_cooktime = source.get("cooktime")
        cooktime_is_explicit = isinstance(raw_cooktime, str) and bool(raw_cooktime.strip())
        cooktime = raw_cooktime.strip().lower() if isinstance(raw_cooktime, str) else "medium"
        if cooktime not in {"fast", "medium", "slow"}:
            cooktime = "medium"
            cooktime_is_explicit = False

        dietary_constraints = tuple(constraints_from_profile(source))
        allergy_values = parse_legacy_allergies(source.get("allergies"))
        seen_allergies = {
            canonical_constraint_value(value) for value in allergy_values
        }
        for constraint in dietary_constraints:
            if constraint.kind != DietaryConstraintKind.INTOLERANCE:
                continue
            if constraint.canonical_value in seen_allergies:
                continue
            seen_allergies.add(constraint.canonical_value)
            allergy_values.append(constraint.value)
        allergies = serialize_legacy_allergies(allergy_values)
        cooking_preferences = parse_cooking_preferences(source)
        prefer_faster_meals = cooking_preferences.prefer_faster_meals
        planning_preferences = parse_planning_preferences(source)
        prefer_familiar_meals = planning_preferences.prefer_familiar_meals

        raw_proteins = source.get("proteins")
        proteins_explicit = "proteins" in source
        proteins: list[str] = []
        if isinstance(raw_proteins, list):
            if len(raw_proteins) == 0:
                return cls(
                    goal=goal,
                    days=days,
                    budget=budget,
                    meals_per_day=meals_per_day,
                    meal_types=meal_types,
                    proteins=[],
                    cooktime=cooktime,
                    allergies=allergies,
                    cooktime_is_explicit=cooktime_is_explicit,
                    proteins_explicit=True,
                    prefer_faster_meals=prefer_faster_meals,
                    prefer_familiar_meals=prefer_familiar_meals,
                    dietary_constraints=dietary_constraints,
                )
            for item in raw_proteins:
                if isinstance(item, str):
                    protein = item.strip().lower()
                    if protein in VALID_PROTEINS and protein not in proteins:
                        proteins.append(protein)
        if not proteins:
            proteins = ["any"]
            proteins_explicit = False

        return cls(
            goal=goal,
            days=days,
            budget=budget,
            meals_per_day=meals_per_day,
            meal_types=meal_types,
            proteins=proteins,
            cooktime=cooktime,
            allergies=allergies,
            cooktime_is_explicit=cooktime_is_explicit,
            proteins_explicit=proteins_explicit,
            prefer_faster_meals=prefer_faster_meals,
            prefer_familiar_meals=prefer_familiar_meals,
            dietary_constraints=dietary_constraints,
        )
