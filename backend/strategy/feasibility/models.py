"""Strategy feasibility models (Sprint 10.11.4)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class FeasibilityStatus(StrEnum):
    FEASIBLE = "FEASIBLE"
    FEASIBLE_WITH_RELAXATION = "FEASIBLE_WITH_RELAXATION"
    INFEASIBLE = "INFEASIBLE"


class FeasibilityIssueCode(StrEnum):
    NO_BATCH_LEFTOVER_CANDIDATE = "NO_BATCH_LEFTOVER_CANDIDATE"
    TIME_LIMIT_REMOVES_REQUIRED_BATCH_CANDIDATES = (
        "TIME_LIMIT_REMOVES_REQUIRED_BATCH_CANDIDATES"
    )
    NO_NOCOOK_ALTERNATIVE = "NO_NOCOOK_ALTERNATIVE"
    NON_COOK_DAY_UNCOVERED = "NON_COOK_DAY_UNCOVERED"
    EXTRA_COOK_DAYS_INSUFFICIENT = "EXTRA_COOK_DAYS_INSUFFICIENT"


class SuggestionCode(StrEnum):
    ADD_COOK_DAY = "ADD_COOK_DAY"
    RELAX_TIME_LIMIT = "RELAX_TIME_LIMIT"
    ALLOW_EXTRA_COOK_DAY = "ALLOW_EXTRA_COOK_DAY"
    CATALOG_COVERAGE_REQUIRED = "CATALOG_COVERAGE_REQUIRED"


class SlotRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    day_index: int
    meal_type: str
    is_cook_day: bool
    coverage_modes: list[str] = Field(default_factory=list)
    source_cook_day: int | None = None
    covered: bool = False
    covered_by: str | None = None


class CandidateCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meal_type: str
    cook_day: int | None = None
    total_meal_type: int = 0
    after_profile_filters: int = 0
    after_time_limit: int = 0
    batch_leftover_before_time: int = 0
    batch_leftover_after_time: int = 0
    nocook_after_time: int = 0
    min_batch_leftover_time: int | None = None


class FeasibilityIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    target_slot: str | None = None
    source_cook_day: int | None = None
    meal_type: str | None = None
    time_limit: int | None = None
    candidate_count: int | None = None
    message: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class SuggestedAdjustment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestion: str
    day: int | None = None
    reason: str = ""
    current: int | None = None
    minimum_supported: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class CatalogGapSignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meal_type: str
    required_properties: list[str] = Field(default_factory=list)
    max_time: int | None = None
    needed_for: str = "non_cook_day"
    source_cook_day: int | None = None
    target_slot: str | None = None


class StrategyFeasibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: FeasibilityStatus
    feasible: bool
    issues: list[FeasibilityIssue] = Field(default_factory=list)
    slot_requirements: list[SlotRequirement] = Field(default_factory=list)
    candidate_coverage: list[CandidateCoverage] = Field(default_factory=list)
    cook_day_gaps: list[str] = Field(default_factory=list)
    suggested_adjustments: list[SuggestedAdjustment] = Field(default_factory=list)
    catalog_gaps: list[CatalogGapSignal] = Field(default_factory=list)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    warning_ru: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python")

    def to_public_warning(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "feasible": self.feasible,
            "issue_codes": [i.code for i in self.issues],
            "cook_day_gaps": list(self.cook_day_gaps),
            "suggested_adjustments": [
                a.model_dump(mode="python") for a in self.suggested_adjustments
            ],
            "catalog_gaps": [g.model_dump(mode="python") for g in self.catalog_gaps],
            "warning_ru": self.warning_ru,
        }
