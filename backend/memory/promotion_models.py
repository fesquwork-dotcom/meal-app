"""API models for memory signal promotion (Sprint 5.21)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PromotionStatus = Literal["promoted", "already_promoted", "already_covered"]


class PromoteMemorySignalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_profile_revision: int = Field(ge=0, le=1_000_000)


class PromoteMemorySignalResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: PromotionStatus
    profile: dict[str, object]
    profile_revision: int
    signal_status: Literal["promoted"] = "promoted"
    constraint_id: str | None = None
