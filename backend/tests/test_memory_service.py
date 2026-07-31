"""Service-level tests for the Memory Engine (real SQLite, deterministic clock)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest

import config
import database
from memory.repository import MemoryRepository
from memory.service import MemoryService, parse_profile_exclusions

NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "memory-service.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    asyncio.run(database.init_db())
    return path


@pytest.fixture
def service():
    return MemoryService()


def _record(service, **kwargs):
    defaults = dict(
        user_id=42,
        strategy_id="s1",
        meal_id="day2_dinner",
        recipe_id="r1",
        reason_code="dislike_ingredient",
        target_ingredient="гречка",
        event_key=None,
        now=NOW,
    )
    defaults.update(kwargs)
    return asyncio.run(service.record_meal_replaced(**defaults))


def test_dislike_creates_observed_avoid_signal(service, db_path):
    result = _record(service, event_key="k1")
    assert result.event_recorded is True
    assert result.signal_updated is True

    signals = asyncio.run(service.list_signals(42))
    assert len(signals) == 1
    assert signals[0].type == "avoid_ingredient"
    assert signals[0].status == "observed"


def test_unavailable_does_not_create_avoid_signal(service, db_path):
    result = _record(service, reason_code="ingredient_unavailable", event_key="k1")
    assert result.event_recorded is True
    assert result.signal_updated is False
    assert asyncio.run(service.list_signals(42)) == []


def test_generic_replacement_creates_no_signal(service, db_path):
    result = _record(service, reason_code="generic", target_ingredient=None, event_key="k1")
    assert result.event_recorded is True
    assert result.signal_updated is False
    assert asyncio.run(service.list_signals(42)) == []


def test_faster_creates_prefer_faster_signal(service, db_path):
    result = _record(service, reason_code="faster", target_ingredient=None, event_key="k1")
    assert result.signal_updated is True
    signals = asyncio.run(service.list_signals(42))
    assert [s.type for s in signals] == ["prefer_faster_meals"]


def test_duplicate_event_key_does_not_duplicate(service, db_path):
    _record(service, event_key="same")
    second = _record(service, event_key="same")
    assert second.deduplicated is True
    assert second.event_recorded is False

    async def _count():
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM memory_events")
            return (await cursor.fetchone())[0]

    assert asyncio.run(_count()) == 1


def test_profile_exclusion_prevents_active_signal(service, db_path):
    asyncio.run(
        database.save_profile(
            42,
            {
                "first_name": "T",
                "budget": 3000,
                "days": 3,
                "persons": 2,
                "proteins": ["any"],
                "goal": "home",
                "cooktime": "medium",
                "allergies": "гречка, орехи",
                "store": "any",
                "meal_types": ["breakfast", "lunch", "dinner"],
            },
        )
    )
    result = _record(service, event_key="k1")
    assert result.signal_updated is False
    assert asyncio.run(service.list_signals(42)) == []


def test_dismiss_then_new_event_recreates_signal(service, db_path):
    _record(service, event_key="k1", now=NOW - timedelta(days=10))
    signal = asyncio.run(service.list_signals(42))[0]
    asyncio.run(service.dismiss_signal(42, signal.id))
    assert asyncio.run(service.list_signals(42)) == []

    # A genuinely later event (after dismissal) may recreate the signal, but old
    # pre-dismiss evidence stays ignored.
    post_dismiss = datetime.now(timezone.utc) + timedelta(days=1)
    _record(service, event_key="k2", now=post_dismiss)
    active = asyncio.run(service.list_signals(42))
    assert len(active) == 1
    assert active[0].status == "observed"
    assert active[0].evidence_count == 1


def test_confirm_sets_confirmed_status(service, db_path):
    _record(service, event_key="k1")
    signal = asyncio.run(service.list_signals(42))[0]
    confirmed = asyncio.run(service.confirm_signal(42, signal.id))
    assert confirmed.status == "confirmed"
    assert confirmed.confidence == 1.0


def test_free_text_reason_not_stored_in_memory(service, db_path):
    # The service API intentionally has no parameter for the free-text comment.
    _record(service, event_key="k1")

    async def _rows():
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM memory_events")
            rows = await cursor.fetchall()
            await cursor.close()
            return rows

    rows = asyncio.run(_rows())
    assert len(rows) == 1
    columns = set(rows[0].keys())
    assert "reason" not in columns
    assert rows[0]["metadata_json"] is None
    assert rows[0]["reason_code"] == "dislike_ingredient"


def test_parse_profile_exclusions_handles_none_token():
    assert parse_profile_exclusions("нет") == set()
    assert parse_profile_exclusions("") == set()
    assert "гречка" in parse_profile_exclusions("Гречка, молоко")
