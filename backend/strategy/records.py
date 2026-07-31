"""Persistence records for weekly strategies (separate from WeeklyStrategy domain model)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class StrategyStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    SUPERSEDED = "superseded"


VALID_STRATEGY_STATUSES: frozenset[str] = frozenset(status.value for status in StrategyStatus)


@dataclass(frozen=True)
class StrategyRecord:
    """Row representation from weekly_strategies table."""

    id: str
    user_id: int
    strategy_version: int
    status: str
    plan_start_date: str
    plan_days: int
    strategy_json: str
    reason_codes_json: str | None
    applied_memory_json: str | None
    applied_cooking_preferences_json: str | None
    applied_behavior_json: str | None
    applied_planning_preferences_json: str | None
    decision_context_json: str | None
    decision_trace_json: str | None
    decision_outcomes_json: str | None
    created_at: str
    updated_at: str
    completed_at: str | None
    superseded_at: str | None
    applied_learned_preferences_json: str | None = None
