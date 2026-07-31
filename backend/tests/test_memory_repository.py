"""Persistence tests for the Memory Engine repository."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import aiosqlite
import pytest

import config
import database
from memory.aggregation import SignalDraft
from memory.exceptions import MemorySignalNotFoundError
from memory.records import MemoryEventRecord
from memory.repository import MemoryRepository

NOW_ISO = datetime(2026, 7, 12, tzinfo=timezone.utc).isoformat()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "memory-test.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    asyncio.run(database.init_db())
    return path


@pytest.fixture
def repository():
    return MemoryRepository()


def _event(key: str, *, user_id: int = 42, reason_code: str = "dislike_ingredient") -> MemoryEventRecord:
    return MemoryEventRecord(
        id=f"evt-{key}",
        user_id=user_id,
        event_type="meal_replaced",
        event_key=key,
        strategy_id="s1",
        meal_id="day2_dinner",
        recipe_id="r1",
        reason_code=reason_code,
        target_type="ingredient",
        target_value="гречка",
        target_label="Гречка",
        metadata_json=None,
        created_at=NOW_ISO,
    )


def test_memory_tables_exist(db_path):
    async def _check():
        async with aiosqlite.connect(db_path) as db:
            names = set()
            for table in ("memory_events", "preference_signals"):
                cursor = await db.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                )
                if await cursor.fetchone():
                    names.add(table)
                await cursor.close()
            return names

    assert asyncio.run(_check()) == {"memory_events", "preference_signals"}


def test_insert_event_is_idempotent_on_event_key(repository, db_path):
    first = asyncio.run(repository.insert_event(_event("dup-key")))
    second = asyncio.run(repository.insert_event(_event("dup-key")))
    assert first is True
    assert second is False

    async def _count():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM memory_events")
            return (await cursor.fetchone())[0]

    assert asyncio.run(_count()) == 1


def test_reason_code_and_canonical_target_stored(repository, db_path):
    asyncio.run(repository.insert_event(_event("k1")))
    events = asyncio.run(
        repository.list_events_for_signal(
            user_id=42, reason_code="dislike_ingredient", target_value="гречка"
        )
    )
    assert len(events) == 1
    assert events[0].reason_code == "dislike_ingredient"
    assert events[0].target_value == "гречка"


def test_upsert_and_get_signal(repository, db_path):
    draft = SignalDraft(
        signal_type="avoid_ingredient",
        target_value="гречка",
        target_label="Гречка",
        status="observed",
        confidence=0.35,
        evidence_count=1,
        first_observed_at=NOW_ISO,
        last_observed_at=NOW_ISO,
    )
    asyncio.run(repository.upsert_signal(42, draft, NOW_ISO))

    signal = asyncio.run(
        repository.get_signal(user_id=42, signal_type="avoid_ingredient", target_value="гречка")
    )
    assert signal is not None
    assert signal.evidence_count == 1
    assert signal.status == "observed"


def test_dismissed_signal_absent_from_active_list(repository, db_path):
    draft = SignalDraft(
        signal_type="avoid_ingredient",
        target_value="гречка",
        target_label="Гречка",
        status="observed",
        confidence=0.35,
        evidence_count=1,
        first_observed_at=NOW_ISO,
        last_observed_at=NOW_ISO,
    )
    asyncio.run(repository.upsert_signal(42, draft, NOW_ISO))
    signal = asyncio.run(
        repository.get_signal(user_id=42, signal_type="avoid_ingredient", target_value="гречка")
    )
    asyncio.run(
        repository.set_status(
            signal_id=signal.id, user_id=42, status="dismissed", confidence=None, now_iso=NOW_ISO
        )
    )

    active = asyncio.run(repository.list_active_signals(42))
    assert active == []


def test_get_signal_by_id_enforces_ownership(repository, db_path):
    draft = SignalDraft(
        signal_type="avoid_ingredient",
        target_value="гречка",
        target_label="Гречка",
        status="observed",
        confidence=0.35,
        evidence_count=1,
        first_observed_at=NOW_ISO,
        last_observed_at=NOW_ISO,
    )
    asyncio.run(repository.upsert_signal(42, draft, NOW_ISO))
    signal = asyncio.run(
        repository.get_signal(user_id=42, signal_type="avoid_ingredient", target_value="гречка")
    )

    with pytest.raises(MemorySignalNotFoundError):
        asyncio.run(repository.get_signal_by_id(signal.id, 99))


def test_list_confirmed_signals_excludes_observed(repository, db_path):
    observed = SignalDraft(
        signal_type="avoid_ingredient",
        target_value="гречка",
        target_label="Гречка",
        status="observed",
        confidence=0.35,
        evidence_count=1,
        first_observed_at=NOW_ISO,
        last_observed_at=NOW_ISO,
    )
    confirmed = SignalDraft(
        signal_type="avoid_ingredient",
        target_value="сельдерей",
        target_label="Сельдерей",
        status="confirmed",
        confidence=1.0,
        evidence_count=3,
        first_observed_at=NOW_ISO,
        last_observed_at=NOW_ISO,
        confirmation_source="automatic",
    )
    asyncio.run(repository.upsert_signal(42, observed, NOW_ISO))
    asyncio.run(repository.upsert_signal(42, confirmed, NOW_ISO))

    records = asyncio.run(repository.list_confirmed_signals(42))
    assert len(records) == 1
    assert records[0].target_value == "сельдерей"


def test_confirm_sets_user_confirmation_source(repository, db_path):
    draft = SignalDraft(
        signal_type="avoid_ingredient",
        target_value="гречка",
        target_label="Гречка",
        status="observed",
        confidence=0.35,
        evidence_count=1,
        first_observed_at=NOW_ISO,
        last_observed_at=NOW_ISO,
    )
    asyncio.run(repository.upsert_signal(42, draft, NOW_ISO))
    signal = asyncio.run(
        repository.get_signal(user_id=42, signal_type="avoid_ingredient", target_value="гречка")
    )
    updated = asyncio.run(
        repository.set_status(
            signal_id=signal.id,
            user_id=42,
            status="confirmed",
            confidence=1.0,
            now_iso=NOW_ISO,
            confirmation_source="user",
        )
    )
    assert updated.confirmation_source == "user"
