"""Profile → CandidateSelectionContext adapter (no recipe knowledge)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from recipes.enums import (
    BudgetClass,
    GoalType,
    MealType,
    ProteinSourceTag,
)
from recipes.models import Ingredient
from recipes.selection.context import CandidateSelectionContext
from recipes.selection.ingredient_resolve import resolve_product_names
from strategy.context import ProfileContext
from strategy.resolvers import COOKTIME_LIMITS_MINUTES

# Profile/strategy goal vocabulary → catalog GoalType
PROFILE_GOAL_TO_CATALOG: dict[str, GoalType] = {
    "weightloss": GoalType.WEIGHT_LOSS,
    "muscle": GoalType.MUSCLE_GAIN,
    "budget": GoalType.BUDGET,
    "healthy": GoalType.BALANCED,
    "home": GoalType.FAMILY,
    "restaurant": GoalType.BALANCED,
}

PROFILE_PROTEIN_TO_TAG: dict[str, ProteinSourceTag] = {
    "chicken": ProteinSourceTag.CHICKEN,
    "beef": ProteinSourceTag.BEEF,
    "pork": ProteinSourceTag.PORK,
    "fish": ProteinSourceTag.FISH,
    "turkey": ProteinSourceTag.TURKEY,
    "eggs": ProteinSourceTag.EGGS,
    "seafood": ProteinSourceTag.FISH,
    "veggie": ProteinSourceTag.LEGUMES,
}

# Heuristic RUB weekly budget → allowed budget classes (temporary mapping).
def budget_float_to_classes(budget: float) -> list[BudgetClass]:
    if budget <= 2500:
        return [BudgetClass.VERY_BUDGET, BudgetClass.BUDGET]
    if budget <= 5000:
        return [BudgetClass.VERY_BUDGET, BudgetClass.BUDGET, BudgetClass.STANDARD]
    if budget <= 9000:
        return [BudgetClass.BUDGET, BudgetClass.STANDARD]
    return [
        BudgetClass.BUDGET,
        BudgetClass.STANDARD,
        BudgetClass.PREMIUM,
    ]


@dataclass
class ProfileAdapterResult:
    context_partial: dict[str, Any]
    unresolved_exclusions: list[str] = field(default_factory=list)


class ProfileToCandidateContextAdapter:
    """Maps ProfileContext fields into selection preferences."""

    def adapt(
        self,
        profile: ProfileContext | dict[str, Any],
        *,
        meal_type: MealType | str,
        ingredients: list[Ingredient] | None = None,
        limit: int = 5,
    ) -> tuple[CandidateSelectionContext, ProfileAdapterResult]:
        if isinstance(profile, dict):
            ctx = ProfileContext.from_profile(profile)
        else:
            ctx = profile

        mt = MealType(meal_type) if not isinstance(meal_type, MealType) else meal_type
        goal = PROFILE_GOAL_TO_CATALOG.get(ctx.goal)

        max_time = COOKTIME_LIMITS_MINUTES.get(ctx.cooktime)
        if ctx.prefer_faster_meals is True and max_time is not None:
            max_time = min(max_time, 30)

        preferred_proteins: set[ProteinSourceTag] = set()
        for protein in ctx.proteins:
            if protein == "any":
                preferred_proteins = set()
                break
            mapped = PROFILE_PROTEIN_TO_TAG.get(protein)
            if mapped:
                preferred_proteins.add(mapped)

        exclusion_names: list[str] = []
        for constraint in ctx.dietary_constraints:
            if constraint.kind.value in {"allergy", "intolerance", "preference"}:
                exclusion_names.append(constraint.canonical_value or constraint.value)
        if ctx.allergies and ctx.allergies.strip().lower() not in {"", "нет", "none"}:
            for part in ctx.allergies.split(","):
                part = part.strip()
                if part and part.lower() not in {"нет", "none"}:
                    exclusion_names.append(part)

        unresolved: list[str] = []
        excluded_ids: set[str] = set()
        if ingredients is not None and exclusion_names:
            resolved = resolve_product_names(exclusion_names, ingredients)
            excluded_ids = resolved.resolved_ids
            unresolved = list(resolved.unresolved)

        prefer_batch = ctx.goal in {"home", "budget", "muscle"}
        allow_leftovers = ctx.goal in {"home", "healthy", "budget", "weightloss"}
        family_mode = ctx.goal == "home"

        partial = {
            "meal_type": mt,
            "limit": limit,
            "goal": goal,
            "allowed_budget_classes": budget_float_to_classes(ctx.budget),
            "max_total_time_minutes": max_time,
            "preferred_protein_sources": preferred_proteins,
            "excluded_ingredient_ids": excluded_ids,
            "prefer_batch_friendly": prefer_batch,
            "allow_leftovers": allow_leftovers,
            "family_mode": family_mode,
        }
        if ctx.prefer_faster_meals:
            partial["preferred_tags"] = {("usage", "quick")}

        result = ProfileAdapterResult(
            context_partial=partial,
            unresolved_exclusions=unresolved,
        )
        context = CandidateSelectionContext.model_validate(partial)
        return context, result
