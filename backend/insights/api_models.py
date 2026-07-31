"""Explicit privacy-safe wire models for Insight Summary."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from insights.evidence_models import (
    EvidenceCoverageStatus,
    InsightLimitation,
    UnavailableReason,
)
from insights.models import (
    InsightAvailability,
    InsightCategory,
    InsightConfidenceLevel,
    InsightEvidenceSource,
    InsightId,
    InsightStatus,
    InsightSummary,
)


class InsightConfidencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    level: InsightConfidenceLevel
    basis: str = Field(max_length=20)


class EvidenceCoveragePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: EvidenceCoverageStatus
    available_since: str | None = Field(default=None, max_length=10)
    oldest_plan_date: str | None = Field(default=None, max_length=10)
    newest_plan_date: str | None = Field(default=None, max_length=10)


class InsightEvidencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    sources: list[InsightEvidenceSource] = Field(default_factory=list, max_length=5)
    evidence_weeks: int = Field(ge=0)
    completed_strategies: int = Field(ge=0)
    positive_events: int = Field(ge=0)
    replacement_events: int = Field(ge=0)
    decision_outcomes: int = Field(ge=0)
    coverage: EvidenceCoveragePayload
    limitations: list[InsightLimitation] = Field(default_factory=list, max_length=7)
    unavailable_reasons: list[UnavailableReason] = Field(
        default_factory=list, max_length=6
    )


class InsightTransparencyPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=80)
    proof_text: str = Field(max_length=200)
    coverage_text: str = Field(max_length=200)
    availability_text: str | None = Field(default=None, max_length=200)
    limitations_text: list[str] = Field(default_factory=list, max_length=7)


class InsightPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: InsightId
    title: str = Field(max_length=80)
    summary: str = Field(max_length=220)
    category: InsightCategory
    confidence: InsightConfidencePayload
    status: InsightStatus
    evidence: InsightEvidencePayload
    available_since: InsightAvailability
    transparency: InsightTransparencyPayload


class InsightSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    generated_at: str = Field(max_length=40)
    insights: list[InsightPayload] = Field(default_factory=list, max_length=10)


def to_insight_summary_response(summary: InsightSummary) -> InsightSummaryResponse:
    return InsightSummaryResponse.model_validate(summary.model_dump(mode="json"))

