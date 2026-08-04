"""WeeklyStrategy → CandidateSelectionContext adapter (strategy is not mutated)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from recipes.enums import GoalType, MealType, ProteinSourceTag, RecipeRole
from recipes.models import Ingredient
from recipes.selection.context import CandidateSelectionContext
from recipes.selection.ingredient_resolve import resolve_product_names
from recipes.selection.profile_adapter import (
    PROFILE_GOAL_TO_CATALOG,
    PROFILE_PROTEIN_TO_TAG,
    budget_float_to_classes,
)
from strategy.models import WeeklyStrategy
from strategy.resolvers import BATCH_COOK_GOALS


@dataclass
class StrategyAdapterResult:
    context_partial: dict[str, Any]
    unresolved_exclusions: list[str] = field(default_factory=list)


class StrategyToCandidateContextAdapter:
    def adapt(
        self,
        strategy: WeeklyStrategy,
        *,
        meal_type: MealType | str,
        ingredients: list[Ingredient] | None = None,
        limit: int = 5,
    ) -> tuple[CandidateSelectionContext, StrategyAdapterResult]:
        mt = MealType(meal_type) if not isinstance(meal_type, MealType) else meal_type
        goal = PROFILE_GOAL_TO_CATALOG.get(strategy.goal)

        preferred_proteins: set[ProteinSourceTag] = set()
        for protein in strategy.preferred_proteins:
            if protein == "any":
                preferred_proteins = set()
                break
            mapped = PROFILE_PROTEIN_TO_TAG.get(protein)
            if mapped:
                preferred_proteins.add(mapped)

        names = list(strategy.excluded_products) + list(
            strategy.availability_avoid_products
        )
        unresolved: list[str] = []
        excluded_ids: set[str] = set()
        if ingredients is not None and names:
            resolved = resolve_product_names(names, ingredients)
            excluded_ids = resolved.resolved_ids
            unresolved = list(resolved.unresolved)

        # Sparse cook days → batch preference
        prefer_batch = (
            strategy.goal in BATCH_COOK_GOALS
            or len(strategy.cook_days) < strategy.days
        )
        desired_roles: list[RecipeRole] = []
        if prefer_batch:
            desired_roles.append(RecipeRole.BATCH_BASE)
        if strategy.leftovers_enabled:
            desired_roles.append(RecipeRole.LEFTOVER_SOURCE)

        partial: dict[str, Any] = {
            "meal_type": mt,
            "limit": limit,
            "goal": goal,
            "allowed_budget_classes": budget_float_to_classes(strategy.budget),
            "max_total_time_minutes": strategy.cooking_time_limit,
            "preferred_protein_sources": preferred_proteins,
            "excluded_ingredient_ids": excluded_ids,
            "prefer_batch_friendly": prefer_batch,
            "allow_leftovers": strategy.leftovers_enabled,
            "family_mode": strategy.goal == "home",
            "desired_roles": desired_roles,
        }
        if strategy.prefer_faster_meals:
            partial["preferred_tags"] = {("usage", "quick")}
            if strategy.cooking_time_limit:
                partial["max_total_time_minutes"] = min(
                    strategy.cooking_time_limit, 30
                )

        result = StrategyAdapterResult(
            context_partial=partial,
            unresolved_exclusions=unresolved,
        )
        context = CandidateSelectionContext.model_validate(partial)
        return context, result
