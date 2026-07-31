"""Stable clock for QA fixtures (Sprint 9.5).

Production and normal request handling continue to use real time.
Only fixture builders and unit tests use this anchor.
"""

from __future__ import annotations

from datetime import date, timedelta

# Fixed calendar independent of "today" so fixtures stay deterministic.
QA_ANCHOR_DATE = date(2026, 7, 13)


def qa_plan_date(*, weeks_before_anchor: int = 0) -> date:
    """Plan start date relative to the QA anchor (not wall-clock today)."""
    if weeks_before_anchor < 0:
        raise ValueError("weeks_before_anchor must be >= 0")
    return QA_ANCHOR_DATE - timedelta(weeks=weeks_before_anchor)
