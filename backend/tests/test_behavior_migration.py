"""Database migration tests for behavior_insights."""

from __future__ import annotations

import asyncio

import aiosqlite
import pytest

import config
import database
from behavior.constants import BEHAVIOR_RULES_VERSION
from behavior.repository import BehaviorRepository
from memory.records import MemoryEventRecord
from memory.repository import MemoryRepository

NOW_ISO = "2026-07-13T12:00:00+00:00"


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "behavior-migration.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    return path


def test_init_db_creates_behavior_table_and_indexes(db_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())

    async def _check():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='behavior_insights'"
            )
            table = await cursor.fetchone()
            await cursor.close()
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='behavior_insights'"
            )
            indexes = {row[0] for row in await cursor.fetchall()}
            await cursor.close()
        return table, indexes

    table, indexes = asyncio.run(_check())
    assert table is not None
    assert "idx_behavior_insights_user_key" in indexes


def test_repeated_init_db_is_safe(db_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    asyncio.run(database.init_db())

    async def _count_tables():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='behavior_insights'"
            )
            return (await cursor.fetchone())[0]

    assert asyncio.run(_count_tables()) == 1


def test_existing_db_without_behavior_gets_table_on_init(tmp_path, monkeypatch):
  path = tmp_path / "legacy.db"
  monkeypatch.setattr(config, "DATABASE_PATH", str(path))

  async def _legacy():
      async with aiosqlite.connect(path) as db:
          await db.execute(database.CREATE_MEMORY_EVENTS_SQL)
          await db.commit()

  asyncio.run(_legacy())
  asyncio.run(database.init_db())

  async def _has_behavior():
      async with aiosqlite.connect(path) as db:
          cursor = await db.execute(
              "SELECT name FROM sqlite_master WHERE type='table' AND name='behavior_insights'"
          )
          return await cursor.fetchone()

  assert asyncio.run(_has_behavior()) is not None


def test_memory_profile_strategy_rows_unchanged_by_behavior_init(db_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())

    memory_repo = MemoryRepository()
    event = MemoryEventRecord(
        id="evt-1",
        user_id=7,
        event_type="meal_replaced",
        event_key="k1",
        strategy_id="s1",
        meal_id="m1",
        recipe_id="r1",
        reason_code="generic",
        target_type=None,
        target_value=None,
        target_label=None,
        metadata_json=None,
        created_at=NOW_ISO,
    )
    asyncio.run(memory_repo.insert_event(event))
    asyncio.run(database.save_profile(7, {"first_name": "A", "budget": 1, "days": 1, "persons": 1, "proteins": ["any"], "goal": "home", "cooktime": "medium", "allergies": "", "store": ""}))

    async def _insert_strategy():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                INSERT INTO weekly_strategies (
                    id, user_id, strategy_version, status, plan_start_date, plan_days,
                    strategy_json, created_at, updated_at
                ) VALUES ('ws-1', 7, 1, 'active', '2026-07-01', 7, '{}', ?, ?)
                """,
                (NOW_ISO, NOW_ISO),
            )
            await db.commit()

    asyncio.run(_insert_strategy())
    asyncio.run(database.init_db())

    async def _counts():
        async with aiosqlite.connect(db_path) as db:
            memory_count = (await (await db.execute("SELECT COUNT(*) FROM memory_events")).fetchone())[0]
            profile_count = (await (await db.execute("SELECT COUNT(*) FROM profiles")).fetchone())[0]
            strategy_count = (await (await db.execute("SELECT COUNT(*) FROM weekly_strategies")).fetchone())[0]
        return memory_count, profile_count, strategy_count

    assert asyncio.run(_counts()) == (1, 1, 1)


def test_rule_version_stored_on_insert(db_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    repo = BehaviorRepository()

    from behavior.constants import BehaviorInsightStatus, BehaviorInsightType
    from behavior.keys import compute_insight_key, new_insight_id
    from behavior.records import BehaviorInsightRecord

    key = compute_insight_key(
        user_id=1,
        insight_type=BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT,
        target_key="recipe-1",
    )
    record = BehaviorInsightRecord(
        id=new_insight_id(),
        user_id=1,
        insight_key=key,
        insight_type=BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT.value,
        target_key="recipe-1",
        target_label=None,
        status=BehaviorInsightStatus.OBSERVED.value,
        confidence=0.35,
        evidence_count=1,
        evidence_window_days=90,
        rule_version=BEHAVIOR_RULES_VERSION,
        first_seen_at=NOW_ISO,
        last_seen_at=NOW_ISO,
        created_at=NOW_ISO,
        updated_at=NOW_ISO,
        confirmed_at=None,
        dismissed_at=None,
        expires_at=None,
    )

    async def _insert():
        await repo._insert(record)
        return await repo.get_by_id(1, record.id)

    loaded = asyncio.run(_insert())
    assert loaded.rule_version == BEHAVIOR_RULES_VERSION
