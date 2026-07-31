"""Integration tests for memory-aware generation pipeline."""

from __future__ import annotations

import asyncio
import json
from datetime import date

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from memory.aggregation import SignalDraft
from memory.constants import ConfirmationSource, SignalStatus, SignalType
from memory.repository import MemoryRepository
from strategy.memory_context import AppliedMemorySnapshot
from tests.menu_fixtures import build_valid_menu_dict
from tests.profile_test_helpers import generate_with_token, issue_preview_token, save_profile


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _configure_auth_and_db(tmp_path, monkeypatch):
    db_path = tmp_path / "memory-pipeline.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


async def _seed_confirmed_avoid(db_path, target: str = "гречка") -> str:
    repo = MemoryRepository()
    await repo.upsert_signal(
        42,
        SignalDraft(
            signal_type=SignalType.AVOID_INGREDIENT.value,
            target_value=target,
            target_label="Гречка",
            status=SignalStatus.CONFIRMED.value,
            confidence=1.0,
            evidence_count=3,
            first_observed_at="2026-01-01T00:00:00+00:00",
            last_observed_at="2026-01-01T00:00:00+00:00",
            confirmation_source=ConfirmationSource.USER.value,
        ),
        "2026-01-01T00:00:00+00:00",
    )
    signal = await repo.get_signal(
        user_id=42,
        signal_type=SignalType.AVOID_INGREDIENT.value,
        target_value=target,
    )
    assert signal is not None
    return signal.id


def test_confirmed_signals_applied_and_snapshot_saved(client, monkeypatch, tmp_path):
    db_path = tmp_path / "memory-pipeline.db"
    asyncio.run(_seed_confirmed_avoid(db_path))

    build_calls: list[object] = []
    original = main._strategy_builder.build_with_reasons_from_inputs

    def capture_build(profile, memory_context=None, behavior_context=None, learned_context=None):
        build_calls.append(memory_context)
        return original(profile, memory_context, behavior_context, learned_context)

    async def fake_generate_menu(**kwargs):
        menu = build_valid_menu_dict(days=kwargs["days"])
        menu["plan_start_date"] = kwargs["plan_start_date"].isoformat()
        return menu

    monkeypatch.setattr(
        main._strategy_builder, "build_with_reasons_from_inputs", capture_build
    )
    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    save_profile(client, expected_revision=0)
    token = issue_preview_token(client, plan_start_date="2026-07-13")
    response = generate_with_token(client, token)
    assert response.status_code == 200
    strategy_id = response.json()["strategy_id"]

    async def _load_applied():
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT applied_memory_json FROM weekly_strategies WHERE id = ?",
                (strategy_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
            return row["applied_memory_json"] if row else None

    raw = asyncio.run(_load_applied())
    snapshot = AppliedMemorySnapshot.from_json(raw)
    assert snapshot is not None
    assert "гречка" in snapshot.avoided_ingredients
    assert build_calls
    assert build_calls[0] is not None
    assert build_calls[0].avoided_ingredients == ("гречка",)


def test_memory_db_failure_uses_empty_context_and_does_not_block(client, monkeypatch):
    async def failing_get_confirmed(_user_id):
        raise RuntimeError("memory unavailable")

    generate_calls = 0

    async def fake_generate_menu(**kwargs):
        nonlocal generate_calls
        generate_calls += 1
        menu = build_valid_menu_dict(days=kwargs["days"])
        menu["plan_start_date"] = kwargs["plan_start_date"].isoformat()
        return menu

    monkeypatch.setattr(main._memory_service, "get_confirmed_signals", failing_get_confirmed)
    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    save_profile(client, expected_revision=0)
    token = issue_preview_token(client, plan_start_date="2026-07-13")
    response = generate_with_token(client, token)
    assert response.status_code == 200
    assert generate_calls == 1


def test_dismiss_during_request_does_not_change_saved_snapshot(client, monkeypatch, tmp_path):
    db_path = tmp_path / "memory-pipeline.db"
    signal_id = asyncio.run(_seed_confirmed_avoid(db_path))

    async def fake_generate_menu(**kwargs):
        await main._memory_service.dismiss_signal(42, signal_id)
        menu = build_valid_menu_dict(days=kwargs["days"])
        menu["plan_start_date"] = kwargs["plan_start_date"].isoformat()
        return menu

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    save_profile(client, expected_revision=0)
    token = issue_preview_token(client, plan_start_date="2026-07-13")
    response = generate_with_token(client, token)
    assert response.status_code == 200
    strategy_id = response.json()["strategy_id"]

    async def _load():
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT applied_memory_json FROM weekly_strategies WHERE id = ?",
                (strategy_id,),
            )
            row = await cursor.fetchone()
            await cursor.close()
            return json.loads(row["applied_memory_json"])

    saved = asyncio.run(_load())
    assert saved["avoided_ingredients"] == ["гречка"]
