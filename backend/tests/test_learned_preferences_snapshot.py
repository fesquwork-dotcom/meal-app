import asyncio
from datetime import date

import aiosqlite
import pytest

import config
import database
from decision.engine import DecisionEngine
from decision.learned_preferences_context import (
    ActiveLearnedPreference,
    LearnedPreferencesContext,
)
from strategy.applied_learned_preferences import (
    AppliedLearnedPreferenceDecision,
    AppliedLearnedPreferencesSnapshot,
)
from strategy.repository import StrategyRepository


@pytest.fixture
def repository(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "snapshot.db"))
    asyncio.run(database.init_db())
    return StrategyRepository()


def _snapshot():
    return AppliedLearnedPreferencesSnapshot(
        enabled=True,
        decisions=[
            AppliedLearnedPreferenceDecision(
                preference_type="prefer_familiar_meals",
                applied=True,
                reason_code="LEARNED_FAMILIAR_MEALS_APPLIED",
                decision_key="planning.prefer_familiar_meals",
            )
        ],
    )


def test_snapshot_round_trip_and_fail_soft_parsing():
    snapshot = _snapshot()
    assert AppliedLearnedPreferencesSnapshot.from_json(snapshot.to_json()) == snapshot
    assert AppliedLearnedPreferencesSnapshot.from_json(None) is None
    assert AppliedLearnedPreferencesSnapshot.from_json("{bad") is None
    assert (
        AppliedLearnedPreferencesSnapshot.from_json(
            '{"version":999,"enabled":true,"decisions":[]}'
        )
        is None
    )


def test_migration_adds_nullable_legacy_column(repository):
    async def _run():
        async with aiosqlite.connect(database.resolve_database_path()) as db:
            cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
            columns = {row[1] for row in await cursor.fetchall()}
            await cursor.close()
            assert "applied_learned_preferences_json" in columns

    asyncio.run(_run())


def test_strategy_save_loads_immutable_snapshot(repository):
    context = LearnedPreferencesContext(
        version=1,
        enabled=True,
        prefer_familiar_meals=True,
        prefer_faster_meals=None,
        source_preferences=(
            ActiveLearnedPreference("prefer_familiar_meals", 1),
        ),
    )
    built = DecisionEngine().evaluate({}, learned_context=context).build_result
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=built.strategy,
            plan_start_date=date(2026, 7, 15),
            applied_learned_preferences=built.applied_learned_preferences,
        )
    )
    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    loaded = repository.load_applied_learned_preferences(record)
    assert loaded == built.applied_learned_preferences
