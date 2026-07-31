"""Calendar lifecycle helpers for persisted weekly strategies."""

from __future__ import annotations

from datetime import date, timedelta

from strategy.records import StrategyRecord


def plan_end_date(plan_start_date: date, plan_days: int) -> date:
    """Last calendar day of the plan (inclusive)."""
    if plan_days < 1:
        raise ValueError("plan_days must be >= 1")
    return plan_start_date + timedelta(days=plan_days - 1)


def is_strategy_completed(
    record: StrategyRecord,
    current_date: date,
) -> bool:
    """True when the plan period ended before current_date (date-only semantics)."""
    start = date.fromisoformat(record.plan_start_date)
    return current_date > plan_end_date(start, record.plan_days)
