"""Immutable snapshot of applied planning preferences for strategy records (Sprint 5.27)."""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

APPLIED_PLANNING_VERSION = 1

FamiliarMealsSource = Literal[
    "profile", "learned_preference", "default", "inferred"
]


class AppliedPlanningPreferences(BaseModel):
    """Recorded planning preference decision at strategy build time."""

    model_config = ConfigDict(extra="ignore")

    version: int = APPLIED_PLANNING_VERSION
    prefer_familiar_meals: bool
    familiar_meals_source: FamiliarMealsSource
    profile_value: bool | None = None

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str | None) -> "AppliedPlanningPreferences | None":
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("applied_planning_preferences_malformed")
            return None
        if not isinstance(parsed, dict):
            return None
        try:
            return cls.model_validate(parsed)
        except ValueError:
            logger.warning("applied_planning_preferences_invalid")
            return None


class AppliedPlanningSettingsResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    prefer_familiar_meals: bool
    familiar_meals_source: FamiliarMealsSource
