"""Persistence of decision_trace_json: migration, save/load, malformed handling."""

import asyncio
from datetime import date

import aiosqlite
import pytest

import config
import database
from decision.engine import DecisionEngine
from strategy.repository import StrategyRepository


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "decision-trace-repo.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    asyncio.run(database.init_db())
    return path


def _save(repository: StrategyRepository, evaluation, *, user_id: int = 7) -> str:
    return asyncio.run(
        repository.save_active(
            user_id=user_id,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 7, 14),
            reason_codes=evaluation.reason_codes,
            applied_memory=evaluation.build_result.applied_memory,
            applied_cooking_preference=evaluation.build_result.applied_cooking_preference,
            applied_behavior=evaluation.build_result.applied_behavior,
            applied_planning_preferences=evaluation.build_result.applied_planning_preferences,
            decision_context=evaluation.decision,
            decision_trace=evaluation.trace,
        )
    )


def test_decision_trace_column_exists(db_path):
    async def _check():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
            rows = await cursor.fetchall()
            await cursor.close()
            return {row[1] for row in rows}

    columns = asyncio.run(_check())
    assert "decision_trace_json" in columns


def test_migration_is_idempotent(db_path):
    asyncio.run(database.init_db())
    asyncio.run(database.init_db())


def test_save_and_load_trace_round_trip(db_path):
    evaluation = DecisionEngine().evaluate({"goal": "budget", "days": 7, "cooktime": "medium"})
    repository = StrategyRepository()
    strategy_id = _save(repository, evaluation)

    record = asyncio.run(repository.get_by_id(strategy_id, 7))
    loaded = repository.load_decision_trace(record)

    assert record.decision_trace_json is not None
    assert loaded is not None
    assert loaded == evaluation.trace
    assert loaded.trace_version == 1


def test_legacy_rows_without_trace_load_fine(db_path):
    evaluation = DecisionEngine().evaluate({"days": 2})
    repository = StrategyRepository()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=9,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 7, 14),
        )
    )

    record = asyncio.run(repository.get_by_id(strategy_id, 9))
    assert record.decision_trace_json is None
    assert repository.load_decision_trace(record) is None
    restored = repository.restore_weekly_strategy(record)
    assert restored.days == 2


def test_malformed_trace_does_not_break_strategy(db_path):
    evaluation = DecisionEngine().evaluate({"goal": "home", "days": 5})
    repository = StrategyRepository()
    strategy_id = _save(repository, evaluation, user_id=11)

    async def _corrupt():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE weekly_strategies SET decision_trace_json = '{broken' WHERE id = ?",
                (strategy_id,),
            )
            await db.commit()

    asyncio.run(_corrupt())
    record = asyncio.run(repository.get_by_id(strategy_id, 11))
    assert repository.load_decision_trace(record) is None
    restored = repository.restore_weekly_strategy(record)
    assert restored.days == 5


def test_unsupported_trace_version_treated_as_unavailable(db_path):
    evaluation = DecisionEngine().evaluate({"goal": "home", "days": 5})
    repository = StrategyRepository()
    strategy_id = _save(repository, evaluation, user_id=12)

    bumped = evaluation.trace.to_json().replace('"trace_version":1', '"trace_version":99')

    async def _bump():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE weekly_strategies SET decision_trace_json = ? WHERE id = ?",
                (bumped, strategy_id),
            )
            await db.commit()

    asyncio.run(_bump())
    record = asyncio.run(repository.get_by_id(strategy_id, 12))
    assert repository.load_decision_trace(record) is None


def test_lifecycle_completion_does_not_mutate_trace(db_path):
    evaluation = DecisionEngine().evaluate({"goal": "budget", "days": 7})
    repository = StrategyRepository()
    strategy_id = _save(repository, evaluation, user_id=13)

    before = asyncio.run(repository.get_by_id(strategy_id, 13)).decision_trace_json
    asyncio.run(repository.mark_completed(strategy_id, 13))
    after = asyncio.run(repository.get_by_id(strategy_id, 13)).decision_trace_json

    assert before == after
    assert before is not None


def test_superseding_strategy_keeps_old_trace(db_path):
    repository = StrategyRepository()
    first = DecisionEngine().evaluate({"goal": "budget", "days": 7})
    first_id = _save(repository, first, user_id=14)
    first_trace = asyncio.run(repository.get_by_id(first_id, 14)).decision_trace_json

    second = DecisionEngine().evaluate({"goal": "healthy", "days": 5})
    _save(repository, second, user_id=14)

    assert asyncio.run(repository.get_by_id(first_id, 14)).decision_trace_json == first_trace
