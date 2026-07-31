"""API-facing models for behavior insights (user-safe projections)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from behavior.constants import BehaviorInsightStatus, BehaviorInsightType, BehaviorSnoozeDuration
from behavior.recommendation_models import BehaviorRecommendationResponse


class BehaviorInsightResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    type: BehaviorInsightType
    status: BehaviorInsightStatus
    title: str
    description: str
    evidence_count: int
    confidence: float
    can_confirm: bool
    can_dismiss: bool
    can_snooze: bool = False
    can_revoke: bool = False
    created_at: str
    updated_at: str
    recommendation: BehaviorRecommendationResponse | None = None
    snoozed_until: str | None = None
    revoked_at: str | None = None


class BehaviorInsightsListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insights: list[BehaviorInsightResponse]
    candidate_count: int
    confirmed_count: int


class BehaviorInsightActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insight: BehaviorInsightResponse


class BehaviorSnoozeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    duration: BehaviorSnoozeDuration


class BehaviorRevokeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    insight: BehaviorInsightResponse
    strategy_effect_changed: bool
    profile_preference_remains_active: bool = False
