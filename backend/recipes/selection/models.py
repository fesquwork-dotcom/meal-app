"""Selection result models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from recipes.models import Recipe
from recipes.selection.codes import reason_text_ru


class SelectionStatus(StrEnum):
    SUCCESS = "success"
    INSUFFICIENT_CANDIDATES = "insufficient_candidates"
    NO_CANDIDATES = "no_candidates"


class RecipeFilterDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    accepted: bool
    reason_codes: list[str] = Field(default_factory=list)


class RecipeScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    components: dict[str, float] = Field(default_factory=dict)
    diversity_penalty: float = 0.0
    active_weights: dict[str, float] = Field(default_factory=dict)

    def to_public_dict(self) -> dict[str, float]:
        out = dict(self.components)
        if self.diversity_penalty:
            out["diversity_penalty"] = self.diversity_penalty
        return out


class RecipeCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    recipe: Recipe
    score: float
    score_breakdown: RecipeScoreBreakdown
    reason_codes: list[str] = Field(default_factory=list)
    matched_preferences: list[str] = Field(default_factory=list)

    def reason_texts_ru(self) -> list[str]:
        return [reason_text_ru(code) for code in self.reason_codes]

    def to_summary(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe.id,
            "name": self.recipe.name,
            "score": round(self.score, 4),
            "reason_codes": list(self.reason_codes),
            "reason_texts_ru": self.reason_texts_ru(),
            "matched_preferences": list(self.matched_preferences),
            "breakdown": {
                k: round(v, 4) for k, v in self.score_breakdown.to_public_dict().items()
            },
        }


class FilterStats(BaseModel):
    model_config = ConfigDict(extra="forbid")

    initial: int = 0
    remaining: int = 0
    removed: dict[str, int] = Field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "initial": self.initial,
            "remaining": self.remaining,
            "removed": dict(self.removed),
        }


class RecipeSelectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    candidates: list[RecipeCandidate] = Field(default_factory=list)
    total_catalog_recipes: int = 0
    after_hard_filters: int = 0
    returned_count: int = 0
    selection_status: SelectionStatus = SelectionStatus.SUCCESS
    filter_stats: FilterStats = Field(default_factory=FilterStats)

    def to_summary(self) -> dict[str, Any]:
        return {
            "selection_status": self.selection_status.value,
            "total_catalog_recipes": self.total_catalog_recipes,
            "after_hard_filters": self.after_hard_filters,
            "returned_count": self.returned_count,
            "filter_stats": self.filter_stats.to_dict(),
            "candidates": [c.to_summary() for c in self.candidates],
        }
