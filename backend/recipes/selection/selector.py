"""RecipeCandidateSelector — hard filter → soft score → ranked top-N."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from recipes.enums import RecipeStatus
from recipes.models import Recipe
from recipes.repository import RecipeRepository
from recipes.selection.context import CandidateSelectionContext
from recipes.selection.hard_filter import RecipeHardFilter
from recipes.selection.models import (
    FilterStats,
    RecipeCandidate,
    RecipeSelectionResult,
    SelectionStatus,
)
from recipes.selection.scorer import RecipeScorer
from recipes.selection.weights import RecipeScoringWeights


class RecipeCandidateSelector:
    def __init__(
        self,
        repository: RecipeRepository | None = None,
        *,
        db_path: Path | str | None = None,
        weights: RecipeScoringWeights | None = None,
        hard_filter: RecipeHardFilter | None = None,
        scorer: RecipeScorer | None = None,
    ) -> None:
        self.repository = repository or RecipeRepository(db_path)
        self.hard_filter = hard_filter or RecipeHardFilter()
        self.scorer = scorer or RecipeScorer(weights)

    async def select(
        self,
        context: CandidateSelectionContext,
        *,
        recipe_pool: list[Recipe] | None = None,
        total_catalog_recipes: int | None = None,
    ) -> RecipeSelectionResult:
        """Rank candidates for one meal slot.

        Optional ``recipe_pool`` avoids repeated DB loads during catalog evaluation.
        Hard filters and soft scoring are unchanged.
        """
        if total_catalog_recipes is None:
            total = await self.repository.count_recipes(RecipeStatus.ACTIVE)
        else:
            total = total_catalog_recipes

        if recipe_pool is None:
            pool = await self.repository.find_candidate_recipes_with_deps(
                meal_type=context.meal_type,
                max_total_time_minutes=None,
                budget_classes=None,
                status=RecipeStatus.ACTIVE,
            )
        else:
            # Preloaded catalog: keep only recipes supporting the requested meal type.
            pool = [
                r
                for r in recipe_pool
                if r.status == RecipeStatus.ACTIVE
                and (
                    any(m.meal_type == context.meal_type for m in r.meal_types)
                    or r.primary_meal_type == context.meal_type
                )
            ]

        return self._rank_pool(context, pool, total)

    def _rank_pool(
        self,
        context: CandidateSelectionContext,
        pool: list[Recipe],
        total: int,
    ) -> RecipeSelectionResult:
        filter_stats = FilterStats(initial=len(pool))
        removed: Counter[str] = Counter()
        accepted: list[Recipe] = []

        for recipe in pool:
            decision = self.hard_filter.evaluate(recipe, context)
            if decision.accepted:
                accepted.append(recipe)
            else:
                for code in decision.reason_codes:
                    removed[code] += 1

        filter_stats.remaining = len(accepted)
        filter_stats.removed = dict(removed)

        candidates: list[RecipeCandidate] = []
        for recipe in accepted:
            score, breakdown, reasons, matched = self.scorer.score(recipe, context)
            candidates.append(
                RecipeCandidate(
                    recipe=recipe,
                    score=score,
                    score_breakdown=breakdown,
                    reason_codes=reasons,
                    matched_preferences=matched,
                )
            )

        candidates.sort(
            key=lambda c: (-c.score, c.recipe.name.lower(), c.recipe.id)
        )
        top = candidates[: context.limit]

        if not accepted:
            status = SelectionStatus.NO_CANDIDATES
        elif len(accepted) < context.limit:
            status = SelectionStatus.INSUFFICIENT_CANDIDATES
        else:
            status = SelectionStatus.SUCCESS

        return RecipeSelectionResult(
            candidates=top,
            total_catalog_recipes=total,
            after_hard_filters=len(accepted),
            returned_count=len(top),
            selection_status=status,
            filter_stats=filter_stats,
        )
