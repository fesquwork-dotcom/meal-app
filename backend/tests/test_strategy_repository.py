import asyncio
from datetime import date, timedelta

import aiosqlite
import pytest

import config
import database
from strategy.exceptions import (
    StrategyNotFoundError,
    StrategyPersistenceError,
    UnsupportedStrategyVersionError,
)
from strategy.repository import StrategyRepository
from tests.strategy_fixtures import build_test_strategy


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "strategy-test.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    asyncio.run(database.init_db())
    return path


@pytest.fixture
def repository():
    return StrategyRepository()


def test_weekly_strategies_table_exists(db_path):
    async def _check():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_strategies'"
            )
            row = await cursor.fetchone()
            await cursor.close()
            return row is not None

    assert asyncio.run(_check())


def test_save_active_persists_strategy(repository, db_path):
    strategy = build_test_strategy()
    plan_start = date(2026, 7, 13)

    strategy_id = asyncio.run(
        repository.save_active(user_id=42, strategy=strategy, plan_start_date=plan_start)
    )

    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    assert record.status == "active"
    assert record.plan_start_date == "2026-07-13"
    assert record.plan_days == strategy.days
    assert record.strategy_version == 5


def test_json_round_trip_restores_weekly_strategy(repository, db_path):
    strategy = build_test_strategy(days=5)
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
        )
    )

    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    restored = repository.restore_weekly_strategy(record)

    assert restored.days == strategy.days
    assert restored.cook_days == strategy.cook_days
    assert restored.goal == strategy.goal


def test_get_active_for_user(repository, db_path):
    strategy = build_test_strategy()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
        )
    )

    active = asyncio.run(repository.get_active_for_user(42))
    assert active is not None
    assert active.id == strategy_id


def test_get_by_id_rejects_other_user(repository, db_path):
    strategy = build_test_strategy()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
        )
    )

    with pytest.raises(StrategyNotFoundError):
        asyncio.run(repository.get_by_id(strategy_id, 99))


def test_previous_active_becomes_superseded(repository, db_path):
    first_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=build_test_strategy(days=3),
            plan_start_date=date(2026, 7, 13),
        )
    )
    second_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=build_test_strategy(days=5),
            plan_start_date=date(2026, 7, 20),
        )
    )

    first = asyncio.run(repository.get_by_id(first_id, 42))
    second = asyncio.run(repository.get_by_id(second_id, 42))
    active = asyncio.run(repository.get_active_for_user(42))

    assert first.status == "superseded"
    assert first.superseded_at is not None
    assert second.status == "active"
    assert active is not None
    assert active.id == second_id


def test_only_one_active_per_user(repository, db_path):
    asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=build_test_strategy(days=3),
            plan_start_date=date(2026, 7, 13),
        )
    )
    asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=build_test_strategy(days=4),
            plan_start_date=date(2026, 7, 20),
        )
    )

    async def _count_active():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM weekly_strategies WHERE user_id = 42 AND status = 'active'"
            )
            count = (await cursor.fetchone())[0]
            await cursor.close()
            return count

    assert asyncio.run(_count_active()) == 1


def test_mark_completed_transition(repository, db_path):
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=build_test_strategy(),
            plan_start_date=date(2026, 7, 13),
        )
    )

    asyncio.run(repository.mark_completed(strategy_id, 42))

    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    assert record.status == "completed"
    assert record.completed_at is not None
    assert asyncio.run(repository.get_active_for_user(42)) is None


def test_timestamps_assigned_on_save(repository, db_path):
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=build_test_strategy(),
            plan_start_date=date(2026, 7, 13),
        )
    )

    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    assert record.created_at
    assert record.updated_at
    assert record.completed_at is None
    assert record.superseded_at is None


def test_malformed_json_raises_controlled_error(repository, db_path):
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=build_test_strategy(),
            plan_start_date=date(2026, 7, 13),
        )
    )

    async def _corrupt():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE weekly_strategies SET strategy_json = ? WHERE id = ?",
                ("not-json", strategy_id),
            )
            await db.commit()

    asyncio.run(_corrupt())

    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    with pytest.raises(StrategyPersistenceError, match="malformed"):
        repository.restore_weekly_strategy(record)


def test_unsupported_strategy_version_raises(repository, db_path):
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=build_test_strategy(),
            plan_start_date=date(2026, 7, 13),
        )
    )

    async def _bump_version():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE weekly_strategies SET strategy_version = ? WHERE id = ?",
                (99, strategy_id),
            )
            await db.commit()

    asyncio.run(_bump_version())

    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    with pytest.raises(UnsupportedStrategyVersionError):
        repository.restore_weekly_strategy(record)


def test_sequential_saves_leave_single_active(repository, db_path):
    for day_offset in range(3):
        asyncio.run(
            repository.save_active(
                user_id=42,
                strategy=build_test_strategy(days=3 + day_offset),
                plan_start_date=date(2026, 7, 13) + timedelta(days=day_offset * 7),
            )
        )

    async def _counts():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM weekly_strategies WHERE user_id = 42 AND status = 'active'"
            )
            active_count = (await cursor.fetchone())[0]
            cursor = await db.execute(
                "SELECT COUNT(*) FROM weekly_strategies WHERE user_id = 42 AND status = 'superseded'"
            )
            superseded_count = (await cursor.fetchone())[0]
            await cursor.close()
            return active_count, superseded_count

    active_count, superseded_count = asyncio.run(_counts())
    assert active_count == 1
    assert superseded_count == 2


def test_init_db_adds_reason_codes_column(db_path):
    async def _column_exists() -> bool:
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
            columns = await cursor.fetchall()
            await cursor.close()
            return any(row[1] == "reason_codes_json" for row in columns)

    assert asyncio.run(_column_exists())


def test_save_active_persists_reason_codes(repository, db_path):
    strategy = build_test_strategy()
    codes = ["GOAL_HOME", "COOK_DAYS_REDUCE_DAILY_WORK"]

    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
            reason_codes=codes,
        )
    )

    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    loaded = repository.load_reason_codes(record)
    assert loaded == codes


def test_legacy_record_with_null_reason_codes(repository, db_path):
    strategy = build_test_strategy()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
        )
    )

    async def _null_reason_codes():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE weekly_strategies SET reason_codes_json = NULL WHERE id = ?",
                (strategy_id,),
            )
            await db.commit()

    asyncio.run(_null_reason_codes())

    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    assert record.reason_codes_json is None
    assert repository.load_reason_codes(record) is None
    restored = repository.restore_weekly_strategy(record)
    assert restored.days == strategy.days


def test_malformed_reason_codes_json_returns_none(repository, db_path):
    strategy = build_test_strategy()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
            reason_codes=["GOAL_HOME"],
        )
    )

    async def _corrupt_json():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE weekly_strategies SET reason_codes_json = ? WHERE id = ?",
                ("not-json", strategy_id),
            )
            await db.commit()

    asyncio.run(_corrupt_json())

    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    assert repository.load_reason_codes(record) is None


def test_applied_memory_json_round_trip(repository, db_path):
    from strategy.memory_context import AppliedMemorySnapshot

    strategy = build_test_strategy()
    snapshot = AppliedMemorySnapshot(
        avoided_ingredients=("гречка",),
        prefer_faster_meals=True,
        decisions=(),
    )
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
            reason_codes=["MEMORY_AVOID_INGREDIENT_APPLIED"],
            applied_memory=snapshot,
        )
    )

    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    restored = repository.load_applied_memory(record)
    assert restored is not None
    assert restored.avoided_ingredients == ("гречка",)
    assert restored.prefer_faster_meals is True


def test_null_applied_memory_json_handled(repository, db_path):
    strategy = build_test_strategy()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
        )
    )

    async def _null_applied_memory():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                "UPDATE weekly_strategies SET applied_memory_json = NULL WHERE id = ?",
                (strategy_id,),
            )
            await db.commit()

    asyncio.run(_null_applied_memory())
    record = asyncio.run(repository.get_by_id(strategy_id, 42))
    assert repository.load_applied_memory(record) is None
