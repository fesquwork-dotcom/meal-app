"""Cross-check WeeklyStrategy against menu generation requests."""

from __future__ import annotations

from dietary_constraints import constraints_from_profile
from meal_types import resolve_meal_types
from shopping.normalization import canonical_ingredient_name
from strategy.effective_exclusions import SAFETY_SOURCES, build_profile_exclusions
from strategy.exceptions import StrategyValidationError
from strategy.memory_apply import PROTEIN_CANONICAL_KEYS
from strategy.models import WeeklyStrategy
from strategy.context import ProfileContext


def _exclusions_context(allergies: str, dietary_constraints: list | None) -> ProfileContext:
    constraints = constraints_from_profile({"dietary_constraints": dietary_constraints or []})
    return ProfileContext(
        goal="home",
        days=1,
        budget=0,
        meals_per_day=1,
        meal_types=["breakfast"],
        proteins=["any"],
        cooktime="medium",
        allergies=allergies,
        dietary_constraints=tuple(constraints),
    )


def _normalize_proteins(proteins: list[str]) -> list[str]:
    normalized: list[str] = []
    for protein in proteins:
        value = protein.strip().lower()
        if value and value not in normalized:
            normalized.append(value)
    return normalized or ["any"]


def validate_strategy_for_request(
    strategy: WeeklyStrategy,
    *,
    days: int,
    budget: float,
    meal_types: list[str] | None,
    meals_per_day: int,
    goal: str,
    proteins: list[str],
    allergies: str,
    dietary_constraints: list | None = None,
) -> None:
    """Ensures strategy and request describe the same planning contract.

    Raises StrategyValidationError when a conflict is detected.
    """
    if strategy.days != days:
        raise StrategyValidationError(
            f"Strategy days ({strategy.days}) do not match request days ({days})",
            code="STRATEGY_DAYS_MISMATCH",
        )

    request_meal_types = resolve_meal_types(meal_types, meals_per_day)
    if strategy.meal_types != request_meal_types:
        raise StrategyValidationError(
            "Strategy meal_types do not match request meal_types",
            code="STRATEGY_MEAL_TYPES_MISMATCH",
        )

    if strategy.goal != goal.strip().lower():
        raise StrategyValidationError(
            f"Strategy goal ({strategy.goal}) does not match request goal ({goal})",
            code="STRATEGY_GOAL_MISMATCH",
        )

    if strategy.budget != float(budget):
        raise StrategyValidationError(
            f"Strategy budget ({strategy.budget}) does not match request budget ({budget})",
            code="STRATEGY_BUDGET_MISMATCH",
        )

    request_proteins = _normalize_proteins(proteins)
    if strategy.preferred_proteins != request_proteins:
        raise StrategyValidationError(
            "Strategy preferred_proteins do not match request proteins",
            code="STRATEGY_PROTEINS_MISMATCH",
        )

    exclusions_context = _exclusions_context(allergies, dietary_constraints)
    effective = build_profile_exclusions(exclusions_context)
    strategy_canonical = {
        canonical_ingredient_name(item) for item in strategy.excluded_products
    }
    request_canonical = {item.canonical_value for item in effective}
    if not request_canonical.issubset(strategy_canonical):
        raise StrategyValidationError(
            "Strategy excluded_products do not include request allergies",
            code="STRATEGY_ALLERGIES_MISMATCH",
        )

    # No safety exclusion (allergy, intolerance, legacy) may be lost.
    safety_canonical = {
        item.canonical_value for item in effective if item.source in SAFETY_SOURCES
    }
    if not safety_canonical.issubset(strategy_canonical):
        raise StrategyValidationError(
            "Strategy excluded_products are missing safety constraints",
            code="STRATEGY_SAFETY_CONSTRAINT_LOST",
        )

    # Preferred proteins must not intersect effective exclusions.
    request_protein_canonicals = {
        canonical_ingredient_name(protein)
        for protein in strategy.preferred_proteins
        if protein != "any"
    }
    mapped_protein_canonicals = {
        canonical_ingredient_name(PROTEIN_CANONICAL_KEYS.get(protein, protein))
        for protein in strategy.preferred_proteins
        if protein != "any"
    }
    if (request_protein_canonicals | mapped_protein_canonicals) & request_canonical:
        raise StrategyValidationError(
            "Strategy preferred proteins intersect effective exclusions",
            code="STRATEGY_PROTEIN_EXCLUSION_OVERLAP",
        )

    if not strategy.meal_types:
        raise StrategyValidationError(
            "Strategy meal_types must not be empty",
            code="STRATEGY_MEAL_TYPES_EMPTY",
        )

    if strategy.generated_at.strip() == "":
        raise StrategyValidationError(
            "Strategy generated_at is required",
            code="STRATEGY_GENERATED_AT_MISSING",
        )
