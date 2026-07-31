"""Models for human-in-the-loop Decision Learning recommendations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LEARNING_RULE_VERSION = 1

LearningRecommendationType = Literal[
    "profile_enable_prefer_familiar_meals",
    "profile_disable_prefer_familiar_meals",
    "profile_enable_prefer_faster_meals",
    "profile_disable_prefer_faster_meals",
    "profile_adjust_cooking_time",
]
LearningRecommendationStatus = Literal[
    "candidate",
    "accepted",
    "dismissed",
    "expired",
]
LearningConfidence = Literal["moderate", "strong"]


class PlanningPreferencePatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    prefer_familiar_meals: bool


class CookingPreferencePatch(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    prefer_faster_meals: bool


class RecommendedProfilePatch(BaseModel):
    """Strict allowlist of profile fields Learning may suggest."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    planning_preferences: PlanningPreferencePatch | None = None
    cooking_preferences: CookingPreferencePatch | None = None
    cooktime: Literal["fast", "medium", "slow"] | None = None


class LearningRecommendation(BaseModel):
    """Persisted recommendation plus deterministic user-facing explanation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str = Field(min_length=1, max_length=80)
    recommendation_type: LearningRecommendationType
    decision_key: str = Field(min_length=1, max_length=80)
    status: LearningRecommendationStatus = "candidate"
    confidence: LearningConfidence
    created_at: str | None = None
    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=240)
    reason: str = Field(min_length=1, max_length=300)
    expected_effect: str = Field(min_length=1, max_length=240)
    what_will_not_change: str = Field(min_length=1, max_length=240)
    recommended_profile_patch: RecommendedProfilePatch
    rule_version: int = LEARNING_RULE_VERSION


class LearningRecommendationCollection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = LEARNING_RULE_VERSION
    recommendations: list[LearningRecommendation] = Field(
        default_factory=list, max_length=10
    )


class LearningRecommendationSummary(BaseModel):
    """Privacy-safe API projection. No raw evidence or trace values."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = LEARNING_RULE_VERSION
    candidate_count: int = Field(ge=0)
    accepted_count: int = Field(ge=0)
    recommendations: list[LearningRecommendation] = Field(
        default_factory=list, max_length=10
    )


class LearningAcceptResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    status: Literal["accepted"]
    recommended_profile_patch: RecommendedProfilePatch


class LearningDismissResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_id: str
    status: Literal["dismissed"]
