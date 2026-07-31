"""Public API projection for trend summaries.

Explicit response models keep the wire contract independent from domain
models: no strategy ids, event ids, revisions, or raw evidence ever leave.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from trends.models import (
    MetricAvailability,
    MetricId,
    TrendConfidenceStatus,
    TrendMetricStatus,
    TrendSummary,
)


class TrendConfidencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: TrendConfidenceStatus
    weeks: int = Field(ge=0)
    completed_strategies: int = Field(ge=0)


class TrendMetricPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: MetricId
    title: str = Field(max_length=80)
    status: TrendMetricStatus
    value: str | None = Field(default=None, max_length=40)
    change: int | None = Field(default=None, ge=-100, le=1000)
    evidence_weeks: int = Field(ge=0)
    confidence: TrendConfidencePayload
    source: str = Field(max_length=80)
    available_since: MetricAvailability
    summary_text: str = Field(max_length=200)
    capability_note: str | None = Field(default=None, max_length=200)


class TrendSummaryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    generated_at: str = Field(max_length=40)
    confidence: TrendConfidencePayload
    metrics: list[TrendMetricPayload] = Field(default_factory=list, max_length=10)


def to_trend_summary_response(summary: TrendSummary) -> TrendSummaryResponse:
    return TrendSummaryResponse.model_validate(summary.model_dump(mode="json"))
