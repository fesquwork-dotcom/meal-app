"""Recipe Candidate Selector (Sprint 10.5).

Independent of Claude menu generation. Hard filters → soft scoring → ranked candidates.
"""

from __future__ import annotations

from recipes.selection.context import CandidateSelectionContext
from recipes.selection.models import (
    RecipeCandidate,
    RecipeFilterDecision,
    RecipeScoreBreakdown,
    RecipeSelectionResult,
    SelectionStatus,
)
from recipes.selection.selector import RecipeCandidateSelector
from recipes.selection.weights import RecipeScoringWeights, DEFAULT_SCORING_WEIGHTS

__all__ = [
    "CandidateSelectionContext",
    "DEFAULT_SCORING_WEIGHTS",
    "RecipeCandidate",
    "RecipeCandidateSelector",
    "RecipeFilterDecision",
    "RecipeScoreBreakdown",
    "RecipeScoringWeights",
    "RecipeSelectionResult",
    "SelectionStatus",
]
