"""Immutable, privacy-safe snapshot of Learned Preference decisions."""

from __future__ import annotations

import json
import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

APPLIED_LEARNED_PREFERENCES_VERSION = 1

LearnedDecisionType = Literal["prefer_familiar_meals", "prefer_fast_meals"]
LearnedDecisionKey = Literal[
    "planning.prefer_familiar_meals",
    "cooking.prefer_faster",
]
LearnedReasonCode = Literal[
    "LEARNED_FAMILIAR_MEALS_APPLIED",
    "LEARNED_FASTER_MEALS_APPLIED",
    "LEARNED_PREFERENCE_IGNORED_PROFILE_PRIORITY",
    "LEARNED_PREFERENCE_REDUNDANT_WITH_PROFILE",
    "LEARNED_PREFERENCE_REDUNDANT_WITH_MEMORY",
    "LEARNED_PREFERENCE_DISABLED_BY_FEATURE_FLAG",
    "LEARNED_PREFERENCE_UNSUPPORTED",
]


class AppliedLearnedPreferenceDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    preference_type: LearnedDecisionType
    applied: bool
    reason_code: LearnedReasonCode
    decision_key: LearnedDecisionKey


class AppliedLearnedPreferencesSnapshot(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = APPLIED_LEARNED_PREFERENCES_VERSION
    enabled: bool
    decisions: list[AppliedLearnedPreferenceDecision] = Field(
        default_factory=list, max_length=2
    )

    @classmethod
    def empty(
        cls, *, enabled: bool = False
    ) -> "AppliedLearnedPreferencesSnapshot":
        return cls(enabled=enabled)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(
        cls, raw: str | None
    ) -> "AppliedLearnedPreferencesSnapshot | None":
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("applied_learned_preferences_unavailable reason=malformed")
            return None
        if (
            not isinstance(parsed, dict)
            or parsed.get("version") != APPLIED_LEARNED_PREFERENCES_VERSION
        ):
            logger.warning(
                "applied_learned_preferences_unavailable reason=unsupported_version"
            )
            return None
        try:
            return cls.model_validate(parsed)
        except ValueError:
            logger.warning("applied_learned_preferences_unavailable reason=invalid")
            return None
