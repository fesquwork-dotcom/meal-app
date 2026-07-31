"""API models for behavior recommendation actions (Sprint 5.27)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RecommendationStatus = Literal["applied", "already_applied", "already_covered"]


class BehaviorRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    can_apply: bool
    applied: bool


class ApplyBehaviorRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_profile_revision: int = Field(ge=0, le=1_000_000)


class ApplyBehaviorRecommendationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: RecommendationStatus
    profile: dict[str, object]
    profile_revision: int
    recommendation_key: str
