"""Domain models for the read-only Trend Engine (Sprint 7.1).

Trends observe history only. Nothing in this package is imported by the
Decision Engine, Learning, or Strategy layers, and trends never feed back
into future decisions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# Public contract version, independent from decision/trace/outcome versions.
TREND_VERSION = 1

MetricId = Literal[
    "replacement_rate",
    "positive_completion",
    "decision_health",
    "recommendation_effectiveness",
    "preference_stability",
]

TrendMetricStatus = Literal[
    "improving",
    "worsening",
    "stable",
    "volatile",
    "insufficient_data",
]

TrendConfidenceStatus = Literal["insufficient_data", "emerging", "established"]

# Metric Capability: the app milestone since which the underlying evidence
# exists. Strategies created before that milestone cannot contribute, and the
# UI can honestly say so instead of mixing old and new plans.
MetricAvailability = Literal["phase_1", "sprint_6_4", "sprint_6_5", "sprint_6_6"]

METRIC_AVAILABILITY: dict[str, MetricAvailability] = {
    "replacement_rate": "phase_1",
    "positive_completion": "sprint_6_5",
    "decision_health": "sprint_6_4",
    "recommendation_effectiveness": "sprint_6_6",
    "preference_stability": "phase_1",
}


class TrendConfidence(BaseModel):
    """Confidence gate result for one metric (or the whole summary)."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    status: TrendConfidenceStatus
    weeks: int = Field(ge=0)
    completed_strategies: int = Field(ge=0)


class TrendMetric(BaseModel):
    """One long-term metric. Aggregate-only: no ids, no raw events."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: MetricId
    title: str = Field(max_length=80)
    status: TrendMetricStatus
    # Quantitative fields are populated only when confidence is established.
    value: str | None = Field(default=None, max_length=40)
    change: int | None = Field(default=None, ge=-100, le=1000)
    evidence_weeks: int = Field(ge=0)
    confidence: TrendConfidence
    source: str = Field(max_length=80)
    available_since: MetricAvailability
    summary_text: str = Field(max_length=200)
    capability_note: str | None = Field(default=None, max_length=200)


class TrendSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    version: int = TREND_VERSION
    generated_at: str = Field(max_length=40)
    confidence: TrendConfidence
    metrics: list[TrendMetric] = Field(default_factory=list, max_length=10)
