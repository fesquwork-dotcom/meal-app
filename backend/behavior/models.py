"""Domain models for behavior insight evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from behavior.constants import BehaviorInsightStatus, BehaviorInsightType


@dataclass(frozen=True)
class BehaviorInsightCandidate:
    """Computed insight state from pure rules (pre-persistence)."""

    insight_type: BehaviorInsightType
    target_key: str | None
    target_label: str | None
    status: BehaviorInsightStatus
    confidence: float
    evidence_count: int
    evidence_window_days: int
    first_seen_at: str
    last_seen_at: str


@dataclass(frozen=True)
class BehaviorEvaluationResult:
    created_count: int
    updated_count: int
    unchanged_count: int
    expired_count: int
    candidate_count: int
    observed_count: int
