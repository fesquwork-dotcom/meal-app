"""Strict HTTP request models for preview and generation."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from strategy.preview_models import ConflictResolutionAction


class StrategyPreviewRequest(BaseModel):
    """Server-owned preview: only runtime fields; Profile loaded from persistence."""

    model_config = ConfigDict(extra="forbid")

    plan_start_date: date | None = None


class StrategyCompareRequest(BaseModel):
    """Compare current strategy snapshot to next preview for the same plan date."""

    model_config = ConfigDict(extra="forbid")

    plan_start_date: date | None = None


class GenerateMenuRequest(BaseModel):
    """Token-only generation: Profile and plan date come from signed preview token."""

    model_config = ConfigDict(extra="forbid")

    preview_token: str | None = None


class ResolveConflictRequest(BaseModel):
    """Server-owned conflict resolution bound to signed preview token."""

    model_config = ConfigDict(extra="forbid")

    preview_token: str = Field(min_length=1)
    conflict_id: str = Field(min_length=13, max_length=40)
    action: ConflictResolutionAction


class PositiveEventRequest(BaseModel):
    """Sprint 6.5 — explicit positive outcome event ("cooked", "suited", ...)."""

    model_config = ConfigDict(extra="forbid")

    event_type: str = Field(min_length=1, max_length=40)
    meal_id: str | None = Field(default=None, max_length=100)


class PositiveEventResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recorded: bool
    deduplicated: bool


class PositiveEventUndoResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    removed: bool
    absent: bool
