"""Immutable snapshot of applied cooking preference for strategy records (Sprint 5.23)."""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from strategy.applied_behavior import AppliedBehaviorSettingsResponse
from strategy.applied_planning import AppliedPlanningSettingsResponse

logger = logging.getLogger(__name__)

APPLIED_COOKING_VERSION = 1

CookingPreferenceSource = Literal[
    "profile", "learned_preference", "memory", "default", "inferred"
]


class AppliedCookingPreference(BaseModel):
    """Recorded cooking preference decision at strategy build time."""

    model_config = ConfigDict(extra="ignore")

    version: int = APPLIED_COOKING_VERSION
    prefer_faster_meals: bool
    source: CookingPreferenceSource
    profile_value: bool | None = None

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str | None) -> "AppliedCookingPreference | None":
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("applied_cooking_preference_malformed")
            return None
        if not isinstance(parsed, dict):
            return None
        try:
            return cls.model_validate(parsed)
        except ValueError:
            logger.warning("applied_cooking_preference_invalid")
            return None


class AppliedCookingSettingsResponse(BaseModel):
    """Public applied cooking settings returned by strategy and preview APIs."""

    model_config = ConfigDict(extra="ignore")

    cooking_time_limit: int
    prefer_faster_meals: bool
    preference_source: CookingPreferenceSource


class AppliedSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    cooking: AppliedCookingSettingsResponse = Field(...)
    behavior: AppliedBehaviorSettingsResponse | None = None
    planning: AppliedPlanningSettingsResponse | None = None
