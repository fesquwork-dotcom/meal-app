"""Centralized soft-scoring weights."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RecipeScoringWeights:
    goal: float = 0.25
    budget: float = 0.10
    time: float = 0.10
    preferred_ingredients: float = 0.10
    preferred_tags: float = 0.08
    protein_source: float = 0.08
    role: float = 0.12
    batch: float = 0.07
    leftover: float = 0.05
    family: float = 0.05

    # Soft penalty strength (applied after weighted average, not in denominator).
    diversity_penalty_strength: float = 0.15

    def as_dict(self) -> dict[str, float]:
        return {
            "goal": self.goal,
            "budget": self.budget,
            "time": self.time,
            "preferred_ingredients": self.preferred_ingredients,
            "preferred_tags": self.preferred_tags,
            "protein_source": self.protein_source,
            "role": self.role,
            "batch": self.batch,
            "leftover": self.leftover,
            "family": self.family,
        }


DEFAULT_SCORING_WEIGHTS = RecipeScoringWeights()

# Lower rank index = more budget-friendly.
BUDGET_CLASS_RANK: dict[str, int] = {
    "very_budget": 0,
    "budget": 1,
    "standard": 2,
    "premium": 3,
}
