"""Frozen persistence records for learned_preferences rows."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LearnedPreferenceRecord:
    id: str
    user_id: int
    type: str
    status: str
    source: str
    version: int
    evidence_json: str
    preference_json: str
    created_at: str
    accepted_at: str | None
    revoked_at: str | None
    archived_at: str | None
    # Sprint 9.4: last dismissed effectiveness cohort. Not a preference status.
    last_review_generation: int | None = None
