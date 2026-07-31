"""Persistence of decision_context_json alongside weekly strategies."""

import asyncio
from datetime import date

import aiosqlite
import pytest

import config
import database
from decision.engine import DecisionEngine
from decision.repository import DecisionRepository
from strategy.repository import StrategyRepository


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "decision-repo.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    asyncio.run(database.init_db())
    return path


def test_decision_context_column_exists(db_path):
    async def _check():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
            rows = await cursor.fetchall()
            await cursor.close()
            return {row[1] for row in rows}

    columns = asyncio.run(_check())
    assert "decision_context_json" in columns


def test_save_active_persists_decision_context(db_path):
    evaluation = DecisionEngine().evaluate({"goal": "home", "days": 3, "budget": 2500.0})
    repository = StrategyRepository()

    strategy_id = asyncio.run(
        repository.save_active(
            user_id=7,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 7, 14),
            reason_codes=evaluation.reason_codes,
            applied_memory=evaluation.build_result.applied_memory,
            applied_cooking_preference=evaluation.build_result.applied_cooking_preference,
            applied_behavior=evaluation.build_result.applied_behavior,
            applied_planning_preferences=evaluation.build_result.applied_planning_preferences,
            decision_context=evaluation.decision,
        )
    )

    record = asyncio.run(repository.get_by_id(strategy_id, 7))
    loaded = repository.load_decision_context(record)

    assert record.decision_context_json is not None
    assert loaded is not None
    assert loaded.decision_version == evaluation.decision.decision_version
    assert loaded.budget.weekly_budget == 2500.0
    assert loaded.days == 3


def test_decision_repository_round_trip():
    decision = DecisionEngine().resolve({"goal": "budget", "days": 5})
    raw = DecisionRepository.dump(decision)
    restored = DecisionRepository.load(raw)
    assert restored is not None
    assert restored.goal == "budget"
    assert restored.shopping.shopping_days == decision.shopping.shopping_days


def test_legacy_rows_without_decision_context_still_load(db_path):
    evaluation = DecisionEngine().evaluate({"days": 2})
    repository = StrategyRepository()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=9,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 7, 14),
        )
    )

    async def _null_decision():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE weekly_strategies SET decision_context_json = NULL WHERE id = ?",
                (strategy_id,),
            )
            await db.commit()

    asyncio.run(_null_decision())
    record = asyncio.run(repository.get_by_id(strategy_id, 9))
    assert repository.load_decision_context(record) is None
    restored = repository.restore_weekly_strategy(record)
    assert restored.days == 2
