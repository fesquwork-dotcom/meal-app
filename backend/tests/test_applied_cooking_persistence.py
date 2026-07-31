"""Tests for applied cooking preference persistence (Sprint 5.23)."""

from __future__ import annotations

import asyncio

import aiosqlite
import pytest

import config
import database
from strategy.applied_cooking import AppliedCookingPreference
from strategy.builder import StrategyBuilder
from strategy.repository import StrategyRepository
from tests.strategy_fixtures import build_test_profile


@pytest.fixture
def repository(db_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    return StrategyRepository()


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "applied-cooking.db"


def test_applied_cooking_json_round_trip():
    snapshot = AppliedCookingPreference(
        prefer_faster_meals=True,
        source="memory",
        profile_value=None,
    )
    restored = AppliedCookingPreference.from_json(snapshot.to_json())
    assert restored == snapshot


def test_malformed_applied_cooking_returns_none():
    assert AppliedCookingPreference.from_json("{not json") is None
    assert AppliedCookingPreference.from_json('{"prefer_faster_meals": "yes"}') is None


def test_applied_cooking_saved_with_strategy(repository):
    strategy = StrategyBuilder().build(build_test_profile())
    applied = AppliedCookingPreference(
        prefer_faster_meals=True,
        source="profile",
        profile_value=True,
    )

    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=__import__("datetime").date(2026, 7, 13),
            applied_cooking_preference=applied,
        )
    )

    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    restored = repository.load_applied_cooking_preference(record)
    assert restored == applied


def test_legacy_record_without_applied_cooking_column_value(repository):
    strategy = StrategyBuilder().build(build_test_profile())
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=__import__("datetime").date(2026, 7, 13),
        )
    )
    record = asyncio.run(repository.get_by_id(strategy_id, 42))

    async def _null_column():
        db_path_resolved = database.resolve_database_path()
        async with aiosqlite.connect(db_path_resolved) as db:
            await db.execute(
                "UPDATE weekly_strategies SET applied_cooking_preferences_json = NULL WHERE id = ?",
                (strategy_id,),
            )
            await db.commit()

    asyncio.run(_null_column())
    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    assert repository.load_applied_cooking_preference(record) is None


def test_applied_cooking_column_exists_after_init(db_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())

    async def _column_exists() -> bool:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
            columns = await cursor.fetchall()
            await cursor.close()
            return any(row[1] == "applied_cooking_preferences_json" for row in columns)

    assert asyncio.run(_column_exists()) is True
