"""Domain models for Learned Preferences (Sprint 9.1).

A Learned Preference is system-owned knowledge that the user explicitly
accepted. It is deliberately separate from Profile, Memory, and Behavior.
No new analytics: candidates are derived only from existing recommendations.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LEARNED_PREFERENCE_VERSION = 1

# V1 types. Only the types backed by an existing recommendation are ever
# produced as candidates; the rest are declared for the closed contract and
# reserved for later sprints (no new rules are introduced here).
LearnedPreferenceType = Literal[
    "prefer_familiar_meals",
    "avoid_unavailable_products",
    "prefer_fast_meals",
    "stable_cook_days",
    "stable_shopping_days",
]

# Append-only lifecycle: candidate -> accepted -> active -> revoked -> archived.
# ``accepted`` is transient; a preference becomes ``active`` only after a
# successful write. ``revoked``/``archived`` are terminal.
LearnedPreferenceStatus = Literal[
    "candidate",
    "accepted",
    "active",
    "revoked",
    "archived",
]

# Origin subsystem that produced the candidate.
LearnedPreferenceSource = Literal["decision_learning"]

LearnedPreferenceConfidence = Literal["moderate", "strong"]


class LearnedPreferenceEvidence(BaseModel):
    """Privacy-safe provenance. Never carries durable identifiers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    source: LearnedPreferenceSource
    confidence: LearnedPreferenceConfidence
    # Human-safe basis label (e.g. the decision area), not a raw decision_id.
    basis: str = Field(min_length=1, max_length=80)


class LearnedPreference(BaseModel):
    """One learned preference plus its deterministic user-facing explanation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    type: LearnedPreferenceType
    status: LearnedPreferenceStatus
    source: LearnedPreferenceSource
    confidence: LearnedPreferenceConfidence
    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(min_length=1, max_length=240)
    evidence: LearnedPreferenceEvidence
    version: int = LEARNED_PREFERENCE_VERSION
    created_at: str | None = None
    accepted_at: str | None = None
    revoked_at: str | None = None
    archived_at: str | None = None
    # Sprint 9.4 review dismiss cohort; null means review never dismissed.
    last_review_generation: int | None = Field(default=None, ge=0, le=12)


class LearnedPreferenceCollection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    version: int = LEARNED_PREFERENCE_VERSION
    preferences: list[LearnedPreference] = Field(default_factory=list, max_length=10)
