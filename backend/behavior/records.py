"""Persistence records for behavior insights."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BehaviorInsightRecord:
    """Row representation from the behavior_insights table."""

    id: str
    user_id: int
    insight_key: str
    insight_type: str
    target_key: str | None
    target_label: str | None
    status: str
    confidence: float
    evidence_count: int
    evidence_window_days: int
    rule_version: int
    first_seen_at: str
    last_seen_at: str
    created_at: str
    updated_at: str
    confirmed_at: str | None
    dismissed_at: str | None
    expires_at: str | None
    recommendation_applied_at: str | None = None
    recommendation_key: str | None = None
    snoozed_at: str | None = None
    snoozed_until: str | None = None
    revoked_at: str | None = None
