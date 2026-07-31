"""Sprint 9.3 — Learned Preference effectiveness domain models.

Read-only retrospective evaluation. Never written to DB. Never consumed by
Decision Engine. All user-facing strings come from allowlisted presentation.
"""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from learned_preferences.models import LearnedPreferenceType

LEARNED_PREFERENCE_EFFECTIVENESS_VERSION = 1

MAX_EFFECTIVENESS_PLANS = 12

# Sprint 9.4: review cohorts of completed applied plans.
# generation = evidence_plans // REVIEW_COHORT_SIZE
# (4–7 → 1, 8–11 → 2, 12 → 3). Dismiss stores that generation.
REVIEW_COHORT_SIZE = 4

LearnedPreferenceEffectivenessStatus = Literal[
    "insufficient_data",
    "emerging",
    "effective",
    "neutral",
    "ineffective",
]

LearnedPreferenceEffectivenessConfidence = Literal[
    "insufficient",
    "partial",
    "established",
]

LearnedPreferenceEffectivenessSummaryCode = Literal[
    "INSUFFICIENT_DATA",
    "EMERGING_POSITIVE",
    "EFFECTIVE_STABLE",
    "NEUTRAL_MIXED",
    "INEFFECTIVE_REPLACEMENTS",
    "UNSUPPORTED_TYPE",
]

LearnedPreferenceEffectivenessLimitation = Literal[
    "SMALL_SAMPLE",
    "NO_CONTROL_GROUP",
    "LEGACY_SNAPSHOTS_EXCLUDED",
    "UNSUPPORTED_TYPE",
    "MIXED_EVIDENCE",
    "ABSENT_POSITIVE_NOT_NEGATIVE",
]


class LearnedPreferencePlanObservation(BaseModel):
    """Privacy-safe aggregate for one finalized plan where preference applied."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    plan_date: date
    preference_applied: bool

    replacement_count: int | None = None
    planned_meal_count: int | None = None

    meal_suited_count: int = Field(ge=0, default=0)
    meal_cooked_count: int = Field(ge=0, default=0)
    plan_completed: bool = False

    # successful | unsuccessful | neutral | insufficient_data | None
    decision_outcome: str | None = None


class LearnedPreferenceEffectiveness(BaseModel):
    """Internal evaluation result before presentation projection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = LEARNED_PREFERENCE_EFFECTIVENESS_VERSION
    preference_type: LearnedPreferenceType

    status: LearnedPreferenceEffectivenessStatus
    evidence_plans: int = Field(ge=0)
    applied_plans: int = Field(ge=0)

    positive_evidence_count: int = Field(ge=0)
    negative_evidence_count: int = Field(ge=0)

    confidence: LearnedPreferenceEffectivenessConfidence
    summary_code: LearnedPreferenceEffectivenessSummaryCode
    limitations: list[LearnedPreferenceEffectivenessLimitation] = Field(
        default_factory=list, max_length=6
    )
    # Cohort index for review re-show (Sprint 9.4). Pure function of evidence_plans.
    generation: int = Field(ge=0, le=MAX_EFFECTIVENESS_PLANS // REVIEW_COHORT_SIZE)


class LearnedPreferenceEffectivenessResponse(BaseModel):
    """Public wire model — titles/summaries only, no internal counters beyond plans."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: LearnedPreferenceEffectivenessStatus
    confidence: LearnedPreferenceEffectivenessConfidence
    evidence_plans: int = Field(ge=0, le=MAX_EFFECTIVENESS_PLANS)
    generation: int = Field(ge=0, le=MAX_EFFECTIVENESS_PLANS // REVIEW_COHORT_SIZE)
    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=240)
    evidence_text: str = Field(min_length=1, max_length=160)
    limitations: list[str] = Field(default_factory=list, max_length=6)
