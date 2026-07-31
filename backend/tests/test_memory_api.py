"""API tests for memory signal endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from memory.service import MemoryService

NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "memory-api.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _seed_avoid_signal(user_id: int = 42, key: str = "k1") -> None:
    asyncio.run(
        MemoryService().record_meal_replaced(
            user_id=user_id,
            strategy_id="s1",
            meal_id="day2_dinner",
            recipe_id="r1",
            reason_code="dislike_ingredient",
            target_ingredient="гречка",
            event_key=key,
            now=NOW,
        )
    )


def _signal_id(client) -> str:
    body = client.get("/api/memory/signals").json()
    return body["signals"][0]["id"]


def test_list_signals_empty(client):
    body = client.get("/api/memory/signals").json()
    assert body == {"signals": []}


def test_list_signals_returns_user_safe_projection(client):
    _seed_avoid_signal()
    body = client.get("/api/memory/signals").json()
    assert len(body["signals"]) == 1
    signal = body["signals"][0]
    assert set(signal.keys()) == {"id", "type", "label", "status", "evidence_count", "confidence"}
    assert signal["type"] == "avoid_ingredient"
    # No raw events, free text, profile, or recipe leaked.
    assert "reason" not in signal
    assert "events" not in signal


def test_confirm_own_signal(client):
    _seed_avoid_signal()
    signal_id = _signal_id(client)
    response = client.post(f"/api/memory/signals/{signal_id}/confirm")
    assert response.status_code == 200
    assert response.json()["signal"]["status"] == "confirmed"


def test_dismiss_own_signal_removes_from_active_list(client):
    _seed_avoid_signal()
    signal_id = _signal_id(client)
    response = client.delete(f"/api/memory/signals/{signal_id}")
    assert response.status_code == 200
    assert client.get("/api/memory/signals").json() == {"signals": []}


def test_foreign_signal_returns_404(client, monkeypatch):
    _seed_avoid_signal(user_id=42)
    signal_id = _signal_id(client)

    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)
    assert client.post(f"/api/memory/signals/{signal_id}/confirm").status_code == 404
    assert client.delete(f"/api/memory/signals/{signal_id}").status_code == 404


def test_unknown_signal_returns_404(client):
    assert client.post("/api/memory/signals/does-not-exist/confirm").status_code == 404


def test_memory_endpoints_require_auth(client, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    assert client.get("/api/memory/signals").status_code == 401
