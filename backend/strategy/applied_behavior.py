"""Immutable snapshot of applied behavior insights for strategy records (Sprint 5.26)."""

from __future__ import annotations

import json
import logging

from pydantic import BaseModel, ConfigDict, Field

from behavior.constants import BehaviorInsightType

logger = logging.getLogger(__name__)

APPLIED_BEHAVIOR_VERSION = 1

BEHAVIOR_AVAILABILITY_FRICTION_APPLIED = "BEHAVIOR_AVAILABILITY_FRICTION_APPLIED"
BEHAVIOR_REDUNDANT_WITH_HIGHER_PRIORITY = "BEHAVIOR_REDUNDANT_WITH_HIGHER_PRIORITY"
BEHAVIOR_RECIPE_PATTERN_NOT_ACTIONABLE = "BEHAVIOR_RECIPE_PATTERN_NOT_ACTIONABLE"
BEHAVIOR_HIGH_REPLACEMENT_RATE_NEEDS_USER_CHOICE = (
    "BEHAVIOR_HIGH_REPLACEMENT_RATE_NEEDS_USER_CHOICE"
)
BEHAVIOR_INSIGHT_INVALID_TARGET = "BEHAVIOR_INSIGHT_INVALID_TARGET"


class AppliedBehaviorDecision(BaseModel):
    model_config = ConfigDict(extra="ignore")

    insight_id: str
    insight_type: BehaviorInsightType
    applied: bool
    reason_code: str
    affected_fields: list[str] = Field(default_factory=list)
    rule_version: int


class AppliedBehaviorSnapshot(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: int = APPLIED_BEHAVIOR_VERSION
    decisions: list[AppliedBehaviorDecision] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str | None) -> "AppliedBehaviorSnapshot | None":
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("applied_behavior_snapshot_malformed")
            return None
        if not isinstance(parsed, dict):
            return None
        version = parsed.get("version")
        if version is not None and version != APPLIED_BEHAVIOR_VERSION:
            logger.warning("applied_behavior_snapshot_unsupported_version version=%s", version)
            return None
        try:
            return cls.model_validate(parsed)
        except ValueError:
            logger.warning("applied_behavior_snapshot_invalid")
            return None

    @classmethod
    def empty(cls) -> "AppliedBehaviorSnapshot":
        return cls(decisions=[])


class AppliedBehaviorSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    applied_count: int = 0
    ignored_count: int = 0
    availability_preferences_applied: bool = False
