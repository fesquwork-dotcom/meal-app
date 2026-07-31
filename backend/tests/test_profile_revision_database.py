"""Database tests for profile revision migration and CAS."""

from __future__ import annotations

import asyncio

import aiosqlite
import pytest

import config
import database
from tests.profile_test_helpers import VALID_PROFILE_BODY


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    db_path = tmp_path / "revision.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    return db_path


async def _revision_column_exists(db_path) -> bool:
    async with aiosqlite.connect(db_path) as db:
        cursor = await db.execute("PRAGMA table_info(profiles)")
        columns = await cursor.fetchall()
        await cursor.close()
        return any(row[1] == "revision" for row in columns)


def test_init_db_adds_revision_column(_db):
    assert asyncio.run(_revision_column_exists(_db)) is True


def test_insert_revision_one(_db):
    async def _run():
        result = await database.save_profile_with_revision(
            7,
            {**VALID_PROFILE_BODY, "first_name": "A"},
            0,
        )
        assert result.success is True
        assert result.revision == 1

    asyncio.run(_run())


def test_stale_update_does_not_increment(_db):
    async def _run():
        await database.save_profile_with_revision(
            7,
            {**VALID_PROFILE_BODY, "first_name": "A"},
            0,
        )
        await database.save_profile_with_revision(
            7,
            {**VALID_PROFILE_BODY, "first_name": "B", "days": 4},
            1,
        )
        stale = await database.save_profile_with_revision(
            7,
            {**VALID_PROFILE_BODY, "first_name": "C", "days": 6},
            1,
        )
        assert stale.success is False
        assert stale.stale is True
        assert stale.current_revision == 2
        profile = await database.get_profile(7)
        assert profile is not None
        assert profile["revision"] == 2
        assert profile["days"] == 4

    asyncio.run(_run())


def test_successful_update_increments_revision(_db):
    async def _run():
        await database.save_profile_with_revision(7, VALID_PROFILE_BODY, 0)
        second = await database.save_profile_with_revision(
            7,
            {**VALID_PROFILE_BODY, "days": 4},
            1,
        )
        assert second.success is True
        assert second.revision == 2

    asyncio.run(_run())
