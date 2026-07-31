from datetime import date

from strategy.lifecycle import is_strategy_completed, plan_end_date
from strategy.records import StrategyRecord


def _record(plan_start: str, plan_days: int, status: str = "active") -> StrategyRecord:
    return StrategyRecord(
        id="test-id",
        user_id=42,
        strategy_version=1,
        status=status,
        plan_start_date=plan_start,
        plan_days=plan_days,
        strategy_json="{}",
        reason_codes_json=None,
        applied_memory_json=None,
        applied_cooking_preferences_json=None,
        applied_behavior_json=None,
        applied_planning_preferences_json=None,
        decision_context_json=None,
        decision_trace_json=None,
        decision_outcomes_json=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        completed_at=None,
        superseded_at=None,
    )


def test_plan_end_date_inclusive():
    assert plan_end_date(date(2026, 7, 13), 3) == date(2026, 7, 15)


def test_is_strategy_completed_after_plan_end():
    record = _record("2026-07-13", 3)
    assert is_strategy_completed(record, date(2026, 7, 16)) is True


def test_is_strategy_completed_on_last_day_is_false():
    record = _record("2026-07-13", 3)
    assert is_strategy_completed(record, date(2026, 7, 15)) is False
