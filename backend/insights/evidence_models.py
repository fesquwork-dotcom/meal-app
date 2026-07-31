"""Evidence and transparency models for insights (Sprint 8.2).

Evidence answers "what data was this conclusion based on"; transparency turns
it into allowlisted user-facing texts. No free-form strings anywhere: every
limitation and unavailable reason is a closed enum value.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

INSIGHT_EVIDENCE_VERSION = 1

InsightEvidenceSource = Literal[
    "trend.replacement_rate",
    "trend.decision_health",
    "trend.preference_stability",
    "trend.recommendation_effectiveness",
    "trend.positive_completion",
    "outcome.successful",
    "delta.total_cost",
]

EvidenceCoverageStatus = Literal["insufficient", "partial", "complete"]

# Closed allowlist: why the evidence for an insight is incomplete.
InsightLimitation = Literal[
    "legacy_strategies",
    "positive_events_missing",
    "not_enough_completed_plans",
    "budget_data_unavailable",
    "menuplan_not_persisted",
    "decision_snapshot_missing",
    "outcome_snapshot_missing",
]

# Closed allowlist: why a conclusion is not possible yet.
UnavailableReason = Literal[
    "need_more_completed_plans",
    "need_positive_events",
    "need_outcomes",
    "need_replacements",
    "metric_not_supported",
    "feature_not_available",
]


class EvidenceCoverage(BaseModel):
    """Deterministic data-coverage tier, independent from Trend confidence."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: EvidenceCoverageStatus
    # ISO dates (YYYY-MM-DD) of the user's own plans; no identifiers.
    available_since: str | None = Field(default=None, max_length=10)
    oldest_plan_date: str | None = Field(default=None, max_length=10)
    newest_plan_date: str | None = Field(default=None, max_length=10)


def _default_coverage() -> EvidenceCoverage:
    return EvidenceCoverage(status="insufficient")


class InsightEvidence(BaseModel):
    """What one insight is based on: sources, counts, coverage, limits."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: Literal[1] = INSIGHT_EVIDENCE_VERSION
    sources: list[InsightEvidenceSource] = Field(default_factory=list, max_length=5)
    evidence_weeks: int = Field(default=0, ge=0)
    completed_strategies: int = Field(default=0, ge=0)
    positive_events: int = Field(default=0, ge=0)
    replacement_events: int = Field(default=0, ge=0)
    decision_outcomes: int = Field(default=0, ge=0)
    coverage: EvidenceCoverage = Field(default_factory=_default_coverage)
    limitations: list[InsightLimitation] = Field(default_factory=list, max_length=7)
    unavailable_reasons: list[UnavailableReason] = Field(
        default_factory=list, max_length=6
    )


class InsightTransparency(BaseModel):
    """Allowlisted user-facing explanation of the evidence behind an insight."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str = Field(max_length=80)
    proof_text: str = Field(max_length=200)
    coverage_text: str = Field(max_length=200)
    availability_text: str | None = Field(default=None, max_length=200)
    limitations_text: list[str] = Field(default_factory=list, max_length=7)
