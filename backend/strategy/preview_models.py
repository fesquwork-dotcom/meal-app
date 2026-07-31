"""API models for strategy preview and conflict resolution."""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from decision.trace_models import DecisionTrace
from decision.user_explanation import DecisionExplanationCollection
from strategy.applied_settings import AppliedSettingsResponse
from strategy.explanation import StrategyExplanation
from strategy.models import WeeklyStrategy

MAX_CONFLICTS_RETURNED = 10
MAX_OPTIONS_PER_CONFLICT = 5


class ConflictResolutionAction(str, Enum):
    DISMISS_MEMORY_SIGNAL = "dismiss_memory_signal"
    REMOVE_PROFILE_PROTEIN = "remove_profile_protein"
    # Applies only to preference-kind constraints. Safety constraints
    # (allergy, intolerance, legacy) are never removable through resolution.
    REMOVE_PROFILE_PREFERENCE = "remove_profile_preference"


class ConflictResolutionOption(BaseModel):
    model_config = ConfigDict(extra="ignore")

    action: str
    label: str
    description: str | None = None


class StrategyConflict(BaseModel):
    model_config = ConfigDict(extra="ignore")

    conflict_id: str
    code: str
    title: str
    description: str
    severity: Literal["blocking", "warning"]
    field: str | None = None
    options: list[ConflictResolutionOption] = Field(default_factory=list)


class AppliedMemorySummary(BaseModel):
    model_config = ConfigDict(extra="ignore")

    has_applied_signals: bool = False
    applied_count: int = 0
    ignored_count: int = 0
    types: list[str] = Field(default_factory=list)


class StrategyPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["ready", "conflict"]
    preview_version: int
    strategy: WeeklyStrategy | None = None
    explanation: StrategyExplanation | None = None
    decision_explanations: DecisionExplanationCollection | None = None
    # Internal hand-off for compare. Pydantic excludes it from all API payloads.
    decision_trace: DecisionTrace | None = Field(default=None, exclude=True)
    conflicts: list[StrategyConflict] = Field(default_factory=list)
    warnings: list[StrategyConflict] = Field(default_factory=list)
    memory_summary: AppliedMemorySummary | None = None
    applied_settings: AppliedSettingsResponse | None = None
    preview_token: str | None = None
    preview_expires_at: str | None = None
    memory_unavailable: bool = False


class ResolveConflictResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["resolved", "requires_input"]
    profile_revision: int | None = None
    requires_new_preview: bool = True
    code: str | None = None
    field: str | None = None
    message: str | None = None
