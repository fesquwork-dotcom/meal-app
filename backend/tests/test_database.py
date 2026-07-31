import asyncio

import pytest

import config
import database
from startup_validation import StartupConfigurationError, validate_startup_configuration


def test_init_db_creates_parent_directory(tmp_path, monkeypatch):
    db_path = tmp_path / "nested" / "app.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))

    resolved = asyncio.run(database.init_db())

    assert resolved == db_path.resolve()
    assert db_path.parent.exists()
    assert db_path.exists()


def test_check_database_ready_after_init(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))

    asyncio.run(database.init_db())

    assert asyncio.run(database.check_database_ready()) is True


def test_init_db_creates_weekly_strategies_table(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))

    asyncio.run(database.init_db())

    async def table_exists() -> bool:
        import aiosqlite

        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='weekly_strategies'"
            )
            row = await cursor.fetchone()
            await cursor.close()
            return row is not None

    async def reason_codes_column_exists() -> bool:
        import aiosqlite

        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
            columns = await cursor.fetchall()
            await cursor.close()
            return any(row[1] == "reason_codes_json" for row in columns)

    async def applied_memory_column_exists() -> bool:
        import aiosqlite

        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA table_info(weekly_strategies)")
            columns = await cursor.fetchall()
            await cursor.close()
            return any(row[1] == "applied_memory_json" for row in columns)

    async def confirmation_source_column_exists() -> bool:
        import aiosqlite

        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("PRAGMA table_info(preference_signals)")
            columns = await cursor.fetchall()
            await cursor.close()
            return any(row[1] == "confirmation_source" for row in columns)

    assert asyncio.run(table_exists()) is True
    assert asyncio.run(reason_codes_column_exists()) is True
    assert asyncio.run(applied_memory_column_exists()) is True
    assert asyncio.run(confirmation_source_column_exists()) is True


def test_check_database_ready_false_when_unavailable(monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", "/nonexistent-root/no-db/app.db")

    assert asyncio.run(database.check_database_ready()) is False


def test_startup_fails_when_database_parent_not_writable(monkeypatch, tmp_path):
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr("startup_validation.os.access", lambda *_args, **_kwargs: False)

    with pytest.raises(StartupConfigurationError, match="not writable"):
        validate_startup_configuration()
