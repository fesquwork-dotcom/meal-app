"""Sprint 6.5 — explicit positive outcome events: validation and isolation."""

import asyncio
from datetime import date

import aiosqlite
import pytest

import config
import database
from decision.engine import DecisionEngine
from memory.positive_events import (
    PositiveEventNotAllowedError,
    PositiveEventService,
    PositiveEventValidationError,
    build_positive_event_key,
)
from memory.repository import MemoryRepository
from strategy.exceptions import StrategyNotFoundError
from strategy.repository import StrategyRepository
from strategy.service import StrategyService


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "positive-events.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    asyncio.run(database.init_db())
    return path


def _save_active(*, user_id: int = 1) -> str:
    evaluation = DecisionEngine().evaluate({"days": 7, "goal": "home"})
    return asyncio.run(
        StrategyRepository().save_active(
            user_id=user_id,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 7, 1),
            reason_codes=evaluation.reason_codes,
            decision_context=evaluation.decision,
            decision_trace=evaluation.trace,
        )
    )


def _events_for(strategy_id: str, user_id: int = 1):
    return asyncio.run(
        MemoryRepository().list_events_for_strategy(
            user_id=user_id, strategy_id=strategy_id
        )
    )


def test_meal_cooked_recorded_with_server_derived_key(db_path):
    strategy_id = _save_active()
    service = PositiveEventService()
    result = asyncio.run(
        service.record_positive_event(
            user_id=1,
            strategy_id=strategy_id,
            event_type="meal_cooked",
            meal_id="d1-breakfast",
        )
    )
    assert result.recorded and not result.deduplicated

    events = _events_for(strategy_id)
    assert len(events) == 1
    assert events[0].event_type == "meal_cooked"
    assert events[0].event_key == build_positive_event_key(
        strategy_id, "meal_cooked", "d1-breakfast"
    )
    assert events[0].reason_code is None
    assert events[0].target_value is None


def test_repeated_mark_is_deduplicated(db_path):
    strategy_id = _save_active()
    service = PositiveEventService()
    for _ in range(2):
        result = asyncio.run(
            service.record_positive_event(
                user_id=1,
                strategy_id=strategy_id,
                event_type="meal_suited",
                meal_id="d1-lunch",
            )
        )
    assert not result.recorded and result.deduplicated
    assert len(_events_for(strategy_id)) == 1


def test_strategy_scoped_events_ignore_meal_id_and_dedupe_per_strategy(db_path):
    strategy_id = _save_active()
    service = PositiveEventService()
    first = asyncio.run(
        service.record_positive_event(
            user_id=1,
            strategy_id=strategy_id,
            event_type="shopping_completed",
            meal_id="should-be-ignored",
        )
    )
    second = asyncio.run(
        service.record_positive_event(
            user_id=1, strategy_id=strategy_id, event_type="shopping_completed"
        )
    )
    assert first.recorded and second.deduplicated

    events = _events_for(strategy_id)
    assert len(events) == 1
    assert events[0].meal_id is None
    assert events[0].event_key == f"positive:{strategy_id}:shopping_completed"


def test_validation_rejects_bad_payloads(db_path):
    strategy_id = _save_active()
    service = PositiveEventService()

    with pytest.raises(PositiveEventValidationError):
        asyncio.run(
            service.record_positive_event(
                user_id=1, strategy_id=strategy_id, event_type="meal_replaced"
            )
        )
    with pytest.raises(PositiveEventValidationError):
        asyncio.run(
            service.record_positive_event(
                user_id=1, strategy_id=strategy_id, event_type="meal_cooked"
            )
        )
    with pytest.raises(PositiveEventValidationError):
        asyncio.run(
            service.record_positive_event(
                user_id=1,
                strategy_id=strategy_id,
                event_type="meal_cooked",
                meal_id="x" * 101,
            )
        )
    assert _events_for(strategy_id) == []


def test_foreign_and_superseded_strategies_are_rejected(db_path):
    service = StrategyService()
    first_eval = DecisionEngine().evaluate({"days": 7})
    first_id = asyncio.run(
        service.save_active_strategy(
            user_id=5,
            strategy=first_eval.strategy,
            plan_start_date=date(2026, 7, 1),
            decision_trace=first_eval.trace,
        )
    )
    second_eval = DecisionEngine().evaluate({"days": 5})
    asyncio.run(
        service.save_active_strategy(
            user_id=5,
            strategy=second_eval.strategy,
            plan_start_date=date(2026, 7, 8),
            decision_trace=second_eval.trace,
        )
    )
    positive_service = PositiveEventService()

    with pytest.raises(StrategyNotFoundError):
        asyncio.run(
            positive_service.record_positive_event(
                user_id=99, strategy_id=first_id, event_type="plan_completed"
            )
        )
    with pytest.raises(PositiveEventNotAllowedError):
        asyncio.run(
            positive_service.record_positive_event(
                user_id=5, strategy_id=first_id, event_type="plan_completed"
            )
        )


def test_completed_strategy_still_accepts_plan_completed(db_path):
    strategy_id = _save_active(user_id=6)
    asyncio.run(StrategyRepository().mark_completed(strategy_id, 6))
    result = asyncio.run(
        PositiveEventService().record_positive_event(
            user_id=6, strategy_id=strategy_id, event_type="plan_completed"
        )
    )
    assert result.recorded


def test_positive_events_never_create_preference_signals(db_path):
    strategy_id = _save_active(user_id=7)
    service = PositiveEventService()
    for event_type, meal_id in (
        ("meal_cooked", "d1-breakfast"),
        ("meal_suited", "d1-breakfast"),
        ("shopping_completed", None),
        ("plan_completed", None),
    ):
        asyncio.run(
            service.record_positive_event(
                user_id=7,
                strategy_id=strategy_id,
                event_type=event_type,
                meal_id=meal_id,
            )
        )

    async def signal_count():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM preference_signals")
            row = await cursor.fetchone()
            await cursor.close()
            return row[0]

    assert asyncio.run(signal_count()) == 0


def test_decision_engine_does_not_import_positive_events():
    import pathlib

    decision_dir = pathlib.Path(__file__).resolve().parents[1] / "decision"
    for module in ("engine.py", "resolver.py", "builder.py", "context.py"):
        source = (decision_dir / module).read_text(encoding="utf-8")
        assert "positive_events" not in source
