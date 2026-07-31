"""Persistence records for memory events and preference signals.

These are storage-layer dataclasses, separate from API/response models.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MemoryEventRecord:
    """Row representation from the memory_events table."""

    id: str
    user_id: int
    event_type: str
    event_key: str
    strategy_id: str | None
    meal_id: str | None
    recipe_id: str | None
    reason_code: str | None
    target_type: str | None
    target_value: str | None
    target_label: str | None
    metadata_json: str | None
    created_at: str


@dataclass(frozen=True)
class PreferenceSignalRecord:
    """Row representation from the preference_signals table."""

    id: str
    user_id: int
    signal_type: str
    target_value: str
    target_label: str | None
    status: str
    confidence: float
    evidence_count: int
    first_observed_at: str | None
    last_observed_at: str | None
    created_at: str
    updated_at: str
    dismissed_at: str | None
    confirmation_source: str | None = None
    promoted_at: str | None = None
    promoted_constraint_id: str | None = None
