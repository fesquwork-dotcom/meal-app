"""Catalog evaluation models (Sprint 10.6)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from recipes.selection.context import CandidateSelectionContext


class ScenarioGroup(StrEnum):
    BASELINE = "baseline"
    GOAL = "goal"
    BUDGET = "budget"
    TIME = "time"
    PROTEIN = "protein"
    DIETARY = "dietary"
    EQUIPMENT = "equipment"
    BATCH = "batch"
    LEFTOVERS = "leftovers"
    FAMILY = "family"
    COMBINED = "combined"
    STRESS = "stress"


class ScenarioCoverageStatus(StrEnum):
    COVERED = "covered"
    WEAK = "weak"
    CRITICAL = "critical"
    EXPECTED_EMPTY = "expected_empty"


class GapSeverity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationType(StrEnum):
    ADD_RECIPE = "add_recipe"
    REVIEW_RECIPE_METADATA = "review_recipe_metadata"
    ADD_MEAL_TYPE = "add_meal_type"
    ADD_ROLE = "add_role"
    REVIEW_GOAL_SCORE = "review_goal_score"
    RETAG_OR_REVIEW_EXISTING_RECIPE = "retag_or_review_existing_recipe"


class EvaluationScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    context: CandidateSelectionContext
    expected_min_candidates: int = Field(ge=0)
    weight: float = Field(default=1.0, gt=0, le=5.0)
    scenario_group: ScenarioGroup
    enabled: bool = True

    @field_validator("id")
    @classmethod
    def _id_slug(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("scenario id must be non-empty")
        return cleaned


class EvaluationScenarioResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str
    scenario_name: str
    scenario_group: ScenarioGroup
    expected_min_candidates: int
    actual_candidates: int
    coverage_ratio: float
    status: ScenarioCoverageStatus
    selection_status: str
    top_candidate_ids: list[str] = Field(default_factory=list)
    top_candidate_names: list[str] = Field(default_factory=list)
    filter_stats: dict[str, Any] = Field(default_factory=dict)
    dominant_filter_reasons: list[str] = Field(default_factory=list)
    average_score: float | None = None
    minimum_score: float | None = None
    maximum_score: float | None = None
    score_spread: float | None = None
    weight: float = 1.0
    meal_type: str | None = None
    goal: str | None = None
    max_total_time_minutes: int | None = None
    allowed_budget_classes: list[str] | None = None


class CatalogGapCluster(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    affected_scenario_ids: list[str] = Field(default_factory=list)
    meal_types: list[str] = Field(default_factory=list)
    goals: list[str] = Field(default_factory=list)
    time_limits: list[int] = Field(default_factory=list)
    budget_classes: list[str] = Field(default_factory=list)
    excluded_ingredients: list[str] = Field(default_factory=list)
    excluded_protein_sources: list[str] = Field(default_factory=list)
    preferred_protein_sources: list[str] = Field(default_factory=list)
    desired_roles: list[str] = Field(default_factory=list)
    severity: GapSeverity
    missing_candidate_count: int = 0
    dominant_filter_reasons: list[str] = Field(default_factory=list)


class RecipeAdditionRecommendation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    priority: int
    recommendation_type: RecommendationType
    suggested_name: str
    primary_meal_type: str | None = None
    supported_meal_types: list[str] = Field(default_factory=list)
    target_goals: list[str] = Field(default_factory=list)
    budget_class: str | None = None
    max_total_time_minutes: int | None = None
    protein_source: str | None = None
    desired_roles: list[str] = Field(default_factory=list)
    required_properties: list[str] = Field(default_factory=list)
    avoid_properties: list[str] = Field(default_factory=list)
    addresses_gap_ids: list[str] = Field(default_factory=list)
    estimated_scenario_impact: int = 0
    reason_codes: list[str] = Field(default_factory=list)
    related_recipe_id: str | None = None


class CatalogCoverageReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total_scenarios: int = 0
    covered_scenarios: int = 0
    weak_scenarios: int = 0
    critical_scenarios: int = 0
    expected_empty_scenarios: int = 0
    weighted_coverage_score: float = 0.0
    coverage_by_meal_type: dict[str, float] = Field(default_factory=dict)
    coverage_by_goal: dict[str, float] = Field(default_factory=dict)
    coverage_by_scenario_group: dict[str, float] = Field(default_factory=dict)
    coverage_by_budget_restriction: dict[str, float] = Field(default_factory=dict)
    coverage_by_time_limit_group: dict[str, float] = Field(default_factory=dict)
    common_filter_failures: dict[str, int] = Field(default_factory=dict)
    common_filter_scenario_hits: dict[str, int] = Field(default_factory=dict)
    catalog_gap_clusters: list[CatalogGapCluster] = Field(default_factory=list)
    recommended_additions: list[RecipeAdditionRecommendation] = Field(
        default_factory=list
    )
    scenario_results: list[EvaluationScenarioResult] = Field(default_factory=list)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
    )
    catalog_recipe_count: int = 0
    catalog_schema_version: str = "1"

    def to_summary_dict(self) -> dict[str, Any]:
        return {
            "total_scenarios": self.total_scenarios,
            "covered_scenarios": self.covered_scenarios,
            "weak_scenarios": self.weak_scenarios,
            "critical_scenarios": self.critical_scenarios,
            "expected_empty_scenarios": self.expected_empty_scenarios,
            "weighted_coverage_score": round(self.weighted_coverage_score, 4),
            "coverage_by_meal_type": {
                k: round(v, 4) for k, v in self.coverage_by_meal_type.items()
            },
            "coverage_by_goal": {
                k: round(v, 4) for k, v in self.coverage_by_goal.items()
            },
            "coverage_by_scenario_group": {
                k: round(v, 4) for k, v in self.coverage_by_scenario_group.items()
            },
            "common_filter_failures": dict(self.common_filter_failures),
            "catalog_recipe_count": self.catalog_recipe_count,
            "generated_at": self.generated_at,
        }
