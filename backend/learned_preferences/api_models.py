"""Explicit privacy-safe wire models for Learned Preferences.

The API rebuilds every field from allowlisted domain values. Stored evidence
internals (decision keys, strategy ids, event ids) are never projected.
"""

from __future__ import annotations

from typing import Literal

import config
from pydantic import BaseModel, ConfigDict, Field

from learned_preferences.models import (
    LEARNED_PREFERENCE_VERSION,
    LearnedPreference,
    LearnedPreferenceCollection,
    LearnedPreferenceConfidence,
    LearnedPreferenceSource,
    LearnedPreferenceStatus,
    LearnedPreferenceType,
)

LearnedPreferencePlanningEffect = Literal["applied", "disabled", "unsupported"]
_SUPPORTED_PLANNING_TYPES = frozenset(
    {"prefer_familiar_meals", "prefer_fast_meals"}
)


class LearnedPreferenceEvidencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: LearnedPreferenceSource
    confidence: LearnedPreferenceConfidence
    basis: str = Field(max_length=80)


class LearnedPreferenceEffectivenessPayload(BaseModel):
    """Privacy-safe effectiveness summary attached to a preference card."""

    model_config = ConfigDict(extra="forbid")

    status: Literal[
        "insufficient_data",
        "emerging",
        "effective",
        "neutral",
        "ineffective",
    ]
    confidence: Literal["insufficient", "partial", "established"]
    evidence_plans: int = Field(ge=0, le=12)
    generation: int = Field(ge=0, le=3)
    title: str = Field(max_length=100)
    summary: str = Field(max_length=240)
    evidence_text: str = Field(max_length=160)
    limitations: list[str] = Field(default_factory=list, max_length=6)


class LearnedPreferencePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(max_length=80)
    type: LearnedPreferenceType
    status: LearnedPreferenceStatus
    confidence: LearnedPreferenceConfidence
    title: str = Field(max_length=100)
    summary: str = Field(max_length=240)
    evidence: LearnedPreferenceEvidencePayload
    version: int
    accepted_at: str | None = Field(default=None, max_length=40)
    revoked_at: str | None = Field(default=None, max_length=40)
    planning_effect: LearnedPreferencePlanningEffect
    effectiveness: LearnedPreferenceEffectivenessPayload | None = None
    # Sprint 9.4: dismissed review cohort. Null = never dismissed.
    last_review_generation: int | None = Field(default=None, ge=0, le=3)

class LearnedPreferencesResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = LEARNED_PREFERENCE_VERSION
    preferences: list[LearnedPreferencePayload] = Field(
        default_factory=list, max_length=10
    )


def to_preference_payload(
    preference: LearnedPreference,
    *,
    effectiveness: LearnedPreferenceEffectivenessPayload | None = None,
) -> LearnedPreferencePayload:
    planning_effect: LearnedPreferencePlanningEffect
    if preference.type not in _SUPPORTED_PLANNING_TYPES:
        planning_effect = "unsupported"
    elif preference.status == "active" and config.ADAPTIVE_PREFERENCES:
        planning_effect = "applied"
    else:
        planning_effect = "disabled"
    return LearnedPreferencePayload(
        id=preference.id,
        type=preference.type,
        status=preference.status,
        confidence=preference.confidence,
        title=preference.title,
        summary=preference.summary,
        evidence=LearnedPreferenceEvidencePayload(
            source=preference.evidence.source,
            confidence=preference.evidence.confidence,
            basis=preference.evidence.basis,
        ),
        version=preference.version,
        accepted_at=preference.accepted_at,
        revoked_at=preference.revoked_at,
        planning_effect=planning_effect,
        effectiveness=effectiveness,
        last_review_generation=(
            preference.last_review_generation
            if preference.status in {"active", "revoked"}
            else None
        ),
    )


def to_preferences_response(
    collection: LearnedPreferenceCollection,
    *,
    effectiveness_by_type: dict[str, LearnedPreferenceEffectivenessPayload | None]
    | None = None,
) -> LearnedPreferencesResponse:
    by_type = effectiveness_by_type or {}
    return LearnedPreferencesResponse(
        version=collection.version,
        preferences=[
            to_preference_payload(
                preference,
                effectiveness=(
                    by_type.get(preference.type)
                    if preference.status in {"active", "revoked"}
                    else None
                ),
            )
            for preference in collection.preferences
        ],
    )
