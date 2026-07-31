"""Domain models for the read-only Insight Engine (Sprint 8.1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from insights.evidence_models import (
    InsightEvidence,
    InsightEvidenceSource,
    InsightTransparency,
)

__all__ = [
    "INSIGHT_VERSION",
    "Insight",
    "InsightAvailability",
    "InsightCategory",
    "InsightConfidence",
    "InsightConfidenceLevel",
    "InsightEvidence",
    "InsightEvidenceSource",
    "InsightId",
    "InsightStatus",
    "InsightSummary",
    "InsightTransparency",
]

INSIGHT_VERSION = 1

InsightCategory = Literal[
    "progress",
    "consistency",
    "adaptation",
    "planning",
    "cost",
]
InsightStatus = Literal["insufficient_data", "informational", "confirmed"]
InsightConfidenceLevel = Literal["low", "medium", "high"]
InsightAvailability = Literal[
    "sprint_6_4",
    "sprint_6_6",
    "sprint_7_1",
    "sprint_7_4",
]
InsightId = Literal[
    "replacement_health",
    "replacement_cost",
    "preference_stability",
    "recommendation_effectiveness",
    "positive_completion",
]
class InsightConfidence(BaseModel):
    """Confidence copied from existing evidence tiers, never recalculated."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: InsightConfidenceLevel
    basis: Literal["trend", "outcome", "delta", "none"]


class Insight(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    id: InsightId
    title: str = Field(max_length=80)
    summary: str = Field(max_length=220)
    category: InsightCategory
    confidence: InsightConfidence
    status: InsightStatus
    evidence: InsightEvidence
    available_since: InsightAvailability
    # Filled by the engine after evidence enrichment; rules leave it empty.
    transparency: InsightTransparency | None = None


class InsightSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = INSIGHT_VERSION
    generated_at: str = Field(max_length=40)
    insights: list[Insight] = Field(default_factory=list, max_length=10)
