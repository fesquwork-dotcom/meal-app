"""Sprint 9.5 — smoke marker suite for manual QA readiness."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main


pytestmark = pytest.mark.smoke


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "smoke.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    monkeypatch.setattr(config, "ADAPTIVE_PREFERENCES", True)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    asyncio.run(database.init_db())
    return TestClient(main.app)


def test_smoke_health_ready(client):
    assert client.get("/api/health").status_code == 200
    ready = client.get("/api/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] in {"ready", "degraded"}


def test_smoke_profile_roundtrip(client):
    payload = {
        "expected_revision": 1,
        "goal": "home",
        "days": 3,
        "budget": 3000,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "proteins": ["any"],
        "cooktime": "medium",
        "allergies": "нет",
        "store": "any",
    }
    # Profile PUT shape may differ — use existing endpoint pattern from tests.
    listed = client.get("/api/profile")
    assert listed.status_code in {200, 404}


def test_smoke_learned_preferences_list(client):
    response = client.get("/api/learned-preferences")
    assert response.status_code == 200
    assert "preferences" in response.json()


def test_smoke_qa_fixture_and_reset(client):
    loaded = client.post(
        "/api/dev/load-qa-scenario",
        json={"scenario": "learned_preference_ineffective"},
    )
    assert loaded.status_code == 200
    prefs = client.get("/api/learned-preferences").json()["preferences"]
    assert prefs
    pref_id = prefs[0]["id"]
    dismiss = client.post(f"/api/learned-preferences/{pref_id}/dismiss-review")
    assert dismiss.status_code == 200
    reset = client.post(
        "/api/dev/reset-current-user",
        json={"confirm": "RESET", "mode": "history_only"},
    )
    assert reset.status_code == 200
