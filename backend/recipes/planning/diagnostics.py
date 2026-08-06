"""Planner diagnostics models and termination inference (Sprint 10.11.1).

Instrumentation only — does not affect beam search / scoring decisions.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TerminationReason(StrEnum):
    NO_CANDIDATES = "NO_CANDIDATES"
    BEAM_EXHAUSTED = "BEAM_EXHAUSTED"
    CONSTRAINT_CONFLICT = "CONSTRAINT_CONFLICT"
    LEFTOVER_CHAIN_FAILED = "LEFTOVER_CHAIN_FAILED"
    COOK_DAY_CONFLICT = "COOK_DAY_CONFLICT"
    MAX_EXTRA_COOK_DAYS = "MAX_EXTRA_COOK_DAYS"
    TIME_LIMIT = "TIME_LIMIT"
    BUDGET_LIMIT = "BUDGET_LIMIT"
    QUALITY_LIMIT = "QUALITY_LIMIT"
    MAX_STATES = "MAX_STATES"
    SUCCESS = "SUCCESS"
    UNKNOWN = "UNKNOWN"


# Weekly / hard-filter codes mapped into termination buckets.
_COOK_DAY_CODES = frozenset({"COOK_DAY_REQUIRED", "COOK_DAY_CONFLICT"})
_TIME_CODES = frozenset({"TIME_LIMIT", "TIME_LIMIT_EXCEEDED"})
_BUDGET_CODES = frozenset({"BUDGET_CLASS", "BUDGET_CLASS_NOT_ALLOWED", "BUDGET_LIMIT"})
_QUALITY_CODES = frozenset({"QUALITY_BELOW_MINIMUM", "QUALITY_LIMIT"})
_LEFTOVER_CODES = frozenset(
    {
        "LEFTOVER_DISABLED",
        "LEFTOVER_OVERCONSUMED",
        "LEFTOVER_BEFORE_SOURCE",
        "LEFTOVER_RECIPE_MISMATCH",
        "LEFTOVER_CHAIN_FAILED",
        "ORPHAN_LEFTOVER",
    }
)
_MAX_EXTRA_COOK_CODES = frozenset({"MAX_EXTRA_COOK_DAYS"})


class RejectedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipe_id: str
    selector_score: float = 0.0
    reject_reason: str
    detail: str = ""


class SlotDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str
    meal_type: str
    day_index: int = 0
    is_cook_day: bool = True
    filled: bool = False
    selected_recipe_id: str | None = None
    failure_reason: str | None = None
    candidate_count_before_filters: int = 0
    candidate_count_after_hard_filters: int = 0
    candidate_count_after_weekly_constraints: int = 0
    candidate_count_after_ranking: int = 0
    selected: str | None = None
    hard_filter_removals: dict[str, int] = Field(default_factory=dict)
    weekly_constraint_removals: dict[str, int] = Field(default_factory=dict)
    best_failed_candidates: list[RejectedCandidate] = Field(default_factory=list)


class PlannerDiagnostics(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Legacy PlanDiagnostics-compatible fields
    states_expanded: int = 0
    states_pruned: int = 0
    candidate_pool_size: int = 0
    beam_width: int = 0
    planning_duration_ms: float = 0.0
    unfilled_slots: list[str] = Field(default_factory=list)
    slot_filter_causes: dict[str, dict[str, int]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    # Sprint 10.11.1 fields
    planning_status: str = "unknown"
    visited_states: int = 0
    expanded_states: int = 0
    pruned_states: int = 0
    beam_iterations: int = 0
    slots_total: int = 0
    slots_completed: int = 0
    failed_slot: str | None = None
    last_successful_slot: str | None = None
    best_partial_score: float | None = None
    termination_reason: str = TerminationReason.UNKNOWN.value
    hard_filter_stats: dict[str, int] = Field(default_factory=dict)
    candidate_statistics: dict[str, Any] = Field(default_factory=dict)
    constraint_statistics: dict[str, int] = Field(default_factory=dict)
    planner_notes: list[str] = Field(default_factory=list)
    slots: list[SlotDiagnostics] = Field(default_factory=list)
    beam_metrics: dict[str, Any] = Field(default_factory=dict)
    search_complexity: dict[str, Any] = Field(default_factory=dict)
    partial_plan: dict[str, Any] | None = None
    best_failed_candidates: list[RejectedCandidate] = Field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump(mode="python")


def _count_in(removals: dict[str, int], codes: frozenset[str]) -> int:
    return sum(int(removals.get(c, 0)) for c in codes)


def infer_termination_reason(
    *,
    planning_status: str,
    failed_slot: SlotDiagnostics | None,
    max_states_hit: bool,
    is_cook_day: bool | None = None,
) -> TerminationReason:
    """Infer why beam search stopped (diagnostics only)."""
    if planning_status == "success":
        return TerminationReason.SUCCESS

    if failed_slot is None:
        if max_states_hit:
            return TerminationReason.MAX_STATES
        return TerminationReason.BEAM_EXHAUSTED

    hard = failed_slot.hard_filter_removals or {}
    weekly = failed_slot.weekly_constraint_removals or {}
    after_hard = int(failed_slot.candidate_count_after_hard_filters)
    after_weekly = int(failed_slot.candidate_count_after_weekly_constraints)
    cook_day = (
        is_cook_day if is_cook_day is not None else bool(failed_slot.is_cook_day)
    )

    quality_hard = _count_in(hard, _QUALITY_CODES)
    time_hard = _count_in(hard, _TIME_CODES)
    budget_hard = _count_in(hard, _BUDGET_CODES)
    hard_total = sum(hard.values()) or 0

    if after_hard == 0:
        if quality_hard > 0 and quality_hard >= max(time_hard, budget_hard, 1):
            return TerminationReason.QUALITY_LIMIT
        if hard_total > 0 and quality_hard == hard_total:
            return TerminationReason.QUALITY_LIMIT
        if quality_hard > 0 and quality_hard == max(hard.values(), default=0):
            return TerminationReason.QUALITY_LIMIT
        return TerminationReason.NO_CANDIDATES

    cook_weekly = _count_in(weekly, _COOK_DAY_CODES)
    leftover_weekly = _count_in(weekly, _LEFTOVER_CODES)
    time_weekly = _count_in(weekly, _TIME_CODES)
    budget_weekly = _count_in(weekly, _BUDGET_CODES)
    max_extra_weekly = _count_in(weekly, _MAX_EXTRA_COOK_CODES)
    weekly_total = sum(weekly.values()) or 0

    if cook_weekly > 0 and cook_weekly >= max(
        leftover_weekly, time_weekly, budget_weekly, max_extra_weekly, 1
    ):
        return TerminationReason.COOK_DAY_CONFLICT

    # Weekly MAX_EXTRA_COOK_DAYS must win over earlier hard-filter TIME/BUDGET
    # counts: those filters shrank the pool, but the final wipe is the extra-day cap.
    if max_extra_weekly > 0 and after_weekly == 0:
        if max_extra_weekly >= max(
            leftover_weekly, time_weekly, budget_weekly, cook_weekly, 1
        ):
            return TerminationReason.MAX_EXTRA_COOK_DAYS

    if (
        not cook_day
        and leftover_weekly > 0
        and leftover_weekly >= max(time_weekly, budget_weekly, cook_weekly, max_extra_weekly, 1)
    ):
        return TerminationReason.LEFTOVER_CHAIN_FAILED

    if time_weekly > 0 and time_weekly >= max(
        budget_weekly, cook_weekly, leftover_weekly, max_extra_weekly, 1
    ):
        return TerminationReason.TIME_LIMIT

    if budget_weekly > 0 and budget_weekly >= max(
        time_weekly, cook_weekly, leftover_weekly, max_extra_weekly, 1
    ):
        return TerminationReason.BUDGET_LIMIT

    # Only attribute TIME/BUDGET via hard filters when weekly did not already
    # explain the wipe (especially MAX_EXTRA_COOK_DAYS).
    if max_extra_weekly == 0:
        if time_hard > 0 and after_weekly == 0 and time_hard >= max(budget_hard, 1):
            return TerminationReason.TIME_LIMIT
        if budget_hard > 0 and after_weekly == 0 and budget_hard >= max(time_hard, 1):
            return TerminationReason.BUDGET_LIMIT

    if after_hard > 0 and after_weekly == 0 and weekly_total > 0:
        return TerminationReason.CONSTRAINT_CONFLICT

    if max_states_hit:
        return TerminationReason.MAX_STATES

    if after_weekly == 0:
        return TerminationReason.BEAM_EXHAUSTED

    return TerminationReason.UNKNOWN


def top_rejected(
    rejected: list[RejectedCandidate], *, limit: int = 5
) -> list[RejectedCandidate]:
    ordered = sorted(
        rejected,
        key=lambda r: (-float(r.selector_score), r.recipe_id, r.reject_reason),
    )
    # Deduplicate by recipe_id keeping highest score first.
    seen: set[str] = set()
    out: list[RejectedCandidate] = []
    for item in ordered:
        if item.recipe_id in seen:
            continue
        seen.add(item.recipe_id)
        out.append(item)
        if len(out) >= limit:
            break
    return out


def merge_counts(dst: dict[str, int], src: dict[str, int]) -> None:
    for key, value in src.items():
        dst[key] = int(dst.get(key, 0)) + int(value)


def map_reject_reason(code: str) -> str:
    """Normalize internal constraint codes for diagnostics counters."""
    if code in _COOK_DAY_CODES:
        return "COOK_DAY_CONFLICT"
    if code in _MAX_EXTRA_COOK_CODES:
        return "MAX_EXTRA_COOK_DAYS"
    if code in _TIME_CODES:
        return "TIME_LIMIT"
    if code in _BUDGET_CODES:
        return "BUDGET_LIMIT"
    if code in _QUALITY_CODES:
        return "QUALITY_LIMIT"
    return code
