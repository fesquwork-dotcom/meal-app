"""Write-once outcome persistence and tolerant legacy loading."""

import asyncio
from datetime import date

import aiosqlite
import pytest

import config
import database
from decision.engine import DecisionEngine
from decision.outcome import evaluate_decision_outcomes
from dataclasses import replace
from memory.repository import MemoryRepository
from strategy.repository import StrategyRepository
from strategy.service import StrategyService
from test_decision_outcomes import _event


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "decision-outcomes.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    asyncio.run(database.init_db())
    return path


def _completed(repository: StrategyRepository, *, user_id: int = 1):
    evaluation = DecisionEngine().evaluate({"days": 7})
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=user_id,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 7, 1),
            reason_codes=evaluation.reason_codes,
            decision_context=evaluation.decision,
            decision_trace=evaluation.trace,
        )
    )
    asyncio.run(repository.mark_completed(strategy_id, user_id))
    return strategy_id, evaluation


def test_migration_adds_outcomes_column(db_path):
    async def columns():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
            rows = await cursor.fetchall()
            await cursor.close()
            return {row[1] for row in rows}

    assert "decision_outcomes_json" in asyncio.run(columns())
    asyncio.run(database.init_db())


def test_save_and_load_outcomes(db_path):
    repository = StrategyRepository()
    strategy_id, evaluation = _completed(repository)
    outcomes = evaluate_decision_outcomes(
        evaluation.trace, [_event(0)], strategy=evaluation.strategy
    )
    assert asyncio.run(
        repository.save_decision_outcomes_if_absent(
            strategy_id=strategy_id, user_id=1, outcomes=outcomes
        )
    )
    record = asyncio.run(repository.get_by_id(strategy_id, 1))
    assert repository.load_decision_outcomes(record) == outcomes


def test_outcomes_are_immutable_after_first_save(db_path):
    repository = StrategyRepository()
    strategy_id, evaluation = _completed(repository)
    first = evaluate_decision_outcomes(
        evaluation.trace, [_event(0)], strategy=evaluation.strategy
    )
    second = evaluate_decision_outcomes(
        evaluation.trace,
        [_event(index) for index in range(9)],
        strategy=evaluation.strategy,
    )
    assert asyncio.run(
        repository.save_decision_outcomes_if_absent(
            strategy_id=strategy_id, user_id=1, outcomes=first
        )
    )
    assert not asyncio.run(
        repository.save_decision_outcomes_if_absent(
            strategy_id=strategy_id, user_id=1, outcomes=second
        )
    )
    record = asyncio.run(repository.get_by_id(strategy_id, 1))
    assert repository.load_decision_outcomes(record) == first


def test_active_strategy_cannot_receive_final_outcomes(db_path):
    repository = StrategyRepository()
    evaluation = DecisionEngine().evaluate({"days": 7})
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=2,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 7, 14),
            decision_trace=evaluation.trace,
        )
    )
    outcomes = evaluate_decision_outcomes(
        evaluation.trace, [_event(0)], strategy=evaluation.strategy
    )
    assert not asyncio.run(
        repository.save_decision_outcomes_if_absent(
            strategy_id=strategy_id, user_id=2, outcomes=outcomes
        )
    )


def test_legacy_null_and_malformed_outcomes_are_nonfatal(db_path):
    repository = StrategyRepository()
    strategy_id, _ = _completed(repository, user_id=3)
    record = asyncio.run(repository.get_by_id(strategy_id, 3))
    assert repository.load_decision_outcomes(record) is None
    assert repository.restore_weekly_strategy(record).days == 7

    async def corrupt():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE weekly_strategies SET decision_outcomes_json = ? WHERE id = ?",
                ("{broken", strategy_id),
            )
            await db.commit()

    asyncio.run(corrupt())
    record = asyncio.run(repository.get_by_id(strategy_id, 3))
    assert repository.load_decision_outcomes(record) is None
    assert repository.restore_weekly_strategy(record).days == 7


def test_superseding_strategy_seals_previous_outcomes_once(db_path):
    service = StrategyService()
    first = DecisionEngine().evaluate({"days": 7, "goal": "home"})
    first_id = asyncio.run(
        service.save_active_strategy(
            user_id=4,
            strategy=first.strategy,
            plan_start_date=date(2026, 7, 1),
            reason_codes=first.reason_codes,
            decision_context=first.decision,
            decision_trace=first.trace,
        )
    )
    asyncio.run(
        MemoryRepository().insert_event(
            replace(_event(0), strategy_id=first_id, user_id=4)
        )
    )
    second = DecisionEngine().evaluate({"days": 5, "goal": "healthy"})
    asyncio.run(
        service.save_active_strategy(
            user_id=4,
            strategy=second.strategy,
            plan_start_date=date(2026, 7, 8),
            reason_codes=second.reason_codes,
            decision_context=second.decision,
            decision_trace=second.trace,
        )
    )
    previous = asyncio.run(StrategyRepository().get_by_id(first_id, 4))
    assert previous.status == "superseded"
    assert StrategyRepository().load_decision_outcomes(previous) is not None
