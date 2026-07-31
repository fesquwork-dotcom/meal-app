"""API tests for strategy preview endpoint."""

from __future__ import annotations

import asyncio

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from memory.aggregation import SignalDraft
from memory.constants import ConfirmationSource, SignalStatus, SignalType
from memory.repository import MemoryRepository
from tests.profile_test_helpers import preview_strategy, save_profile


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _configure_auth_and_db(tmp_path, monkeypatch):
    db_path = tmp_path / "preview-api.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


async def _seed_fish_avoid():
    repo = MemoryRepository()
    await repo.upsert_signal(
        42,
        SignalDraft(
            signal_type=SignalType.AVOID_INGREDIENT.value,
            target_value="рыба",
            target_label="Рыба",
            status=SignalStatus.CONFIRMED.value,
            confidence=1.0,
            evidence_count=3,
            first_observed_at="2026-01-01T00:00:00+00:00",
            last_observed_at="2026-01-01T00:00:00+00:00",
            confirmation_source=ConfirmationSource.USER.value,
        ),
        "2026-01-01T00:00:00+00:00",
    )


def test_ready_preview_returns_strategy_and_token(client):
    save_profile(client, expected_revision=0)
    response = preview_strategy(client, plan_start_date="2026-07-13")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["preview_token"]
    assert body["preview_expires_at"]
    assert "preview_fingerprint" not in body


def test_preview_accepts_empty_body(client):
    save_profile(client, expected_revision=0)
    response = client.post("/api/strategy/preview", json={})
    assert response.status_code == 200
    assert response.json()["preview_token"]


def test_preview_rejects_legacy_profile_fields(client):
    save_profile(client, expected_revision=0)
    response = client.post(
        "/api/strategy/preview",
        json={"days": 5, "budget": 9999, "proteins": ["fish"]},
    )
    assert response.status_code == 422


def test_preview_requires_persisted_profile(client):
    response = preview_strategy(client)
    assert response.status_code == 422
    assert response.json()["code"] == "PROFILE_REQUIRED"


def test_conflict_preview_without_claude_or_strategy_record(client, monkeypatch):
    save_profile(client, expected_revision=0, proteins=["fish"])
    asyncio.run(_seed_fish_avoid())
    claude_calls = 0

    async def fake_generate_menu(**_kwargs):
        nonlocal claude_calls
        claude_calls += 1
        return {}

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = preview_strategy(client)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "conflict"
    assert claude_calls == 0


def test_preview_uses_persisted_profile_not_request_days(client):
    save_profile(client, expected_revision=0, days=3)
    response = preview_strategy(client)
    assert response.status_code == 200
    assert response.json()["strategy"]["days"] == 3


def test_memory_unavailable_preview_continues(client, monkeypatch):
    save_profile(client, expected_revision=0)

    async def failing_get_confirmed(_user_id):
        raise RuntimeError("memory down")

    monkeypatch.setattr(main._memory_service, "get_confirmed_signals", failing_get_confirmed)
    response = preview_strategy(client)
    assert response.status_code == 200
    assert response.json()["memory_unavailable"] is True


def test_preview_does_not_create_strategy_record(client, tmp_path):
    db_path = tmp_path / "preview-api.db"
    save_profile(client, expected_revision=0)
    preview_strategy(client)

    async def _count():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM weekly_strategies")
            return (await cursor.fetchone())[0]

    assert asyncio.run(_count()) == 0
