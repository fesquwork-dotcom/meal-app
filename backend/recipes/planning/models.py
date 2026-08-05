"""Weekly planner domain models (independent of MenuPlan)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from recipes.planning.diagnostics import PlannerDiagnostics


class PlanStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    NO_PLAN = "no_plan"


# Sprint 10.11.1: PlanDiagnostics is an alias of PlannerDiagnostics.
PlanDiagnostics = PlannerDiagnostics


class WeeklyPlannedMeal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    day_index: int
    meal_type: str
    recipe_id: str
    recipe_name: str = ""
    selection_score: float = 0.0
    selector_rank: int | None = None
    is_leftover: bool = False
    source_slot_id: str | None = None
    cooking_instance_id: str
    requires_cooking: bool = True
    selector_reasons: list[str] = Field(default_factory=list)
    planner_reasons: list[str] = Field(default_factory=list)
    alternatives: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Top alternate selector candidates (id/score/rank) for diagnostics",
    )


class CookingInstance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cooking_instance_id: str
    recipe_id: str
    source_slot_id: str
    servings_cooked: int = 1
    servings_consumed: int = 1
    leftover_slots: list[str] = Field(default_factory=list)


class ScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    selector_quality: float = 0.0
    recipe_diversity: float = 0.0
    protein_diversity: float = 0.0
    relation_score: float = 0.0
    strategy_alignment: float = 0.0
    batch_efficiency: float = 0.0
    ingredient_reuse: float = 0.0
    repeat_penalty: float = 0.0

    def as_dict(self) -> dict[str, float]:
        return {
            "selector_quality": round(self.selector_quality, 4),
            "recipe_diversity": round(self.recipe_diversity, 4),
            "protein_diversity": round(self.protein_diversity, 4),
            "relation_score": round(self.relation_score, 4),
            "strategy_alignment": round(self.strategy_alignment, 4),
            "batch_efficiency": round(self.batch_efficiency, 4),
            "ingredient_reuse": round(self.ingredient_reuse, 4),
            "repeat_penalty": round(self.repeat_penalty, 4),
        }


class WeeklyRecipePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str
    status: PlanStatus
    strategy_id: str | None = None
    days: int
    meal_types: list[str] = Field(default_factory=list)
    meals: list[WeeklyPlannedMeal] = Field(default_factory=list)
    cooking_instances: list[CookingInstance] = Field(default_factory=list)
    score: float = 0.0
    score_breakdown: ScoreBreakdown = Field(default_factory=ScoreBreakdown)
    explanation: dict[str, Any] = Field(default_factory=dict)
    diagnostics: PlannerDiagnostics = Field(default_factory=PlannerDiagnostics)
    warnings: list[str] = Field(default_factory=list)
    violations: list[dict[str, Any]] = Field(default_factory=list)

    def meal_by_slot(self) -> dict[str, WeeklyPlannedMeal]:
        return {m.slot_id: m for m in self.meals}

    def to_summary(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "status": self.status.value,
            "days": self.days,
            "meal_types": list(self.meal_types),
            "score": round(self.score, 4),
            "score_breakdown": self.score_breakdown.as_dict(),
            "meals": [
                {
                    "slot_id": m.slot_id,
                    "recipe_id": m.recipe_id,
                    "recipe_name": m.recipe_name,
                    "is_leftover": m.is_leftover,
                    "requires_cooking": m.requires_cooking,
                    "source_slot_id": m.source_slot_id,
                    "cooking_instance_id": m.cooking_instance_id,
                    "selection_score": round(m.selection_score, 4),
                    "selector_rank": m.selector_rank,
                    "planner_reasons": list(m.planner_reasons),
                    "selector_reasons": list(m.selector_reasons),
                }
                for m in self.meals
            ],
            "cooking_instances": [c.model_dump() for c in self.cooking_instances],
            "explanation": self.explanation,
            "diagnostics": self.diagnostics.model_dump(),
            "warnings": list(self.warnings),
            "violations": list(self.violations),
        }
