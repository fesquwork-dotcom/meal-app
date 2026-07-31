"""Tests for unified API error envelope (Sprint 5.20)."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from tests.profile_test_helpers import save_profile


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "unified-errors.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    return TestClient(main.app)


def _error_envelope_keys(body: dict) -> set[str]:
    return set(body.keys())


def test_request_validation_envelope(client):
    response = client.post("/api/strategy/resolve-conflict", json={})
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "REQUEST_VALIDATION_ERROR"
    assert body["message"]
    assert isinstance(body.get("field_errors"), list)
    assert len(body["field_errors"]) > 0
    assert "detail" not in body


def test_profile_stale_envelope(client):
    save_profile(client, expected_revision=0)
    save_profile(client, expected_revision=1, days=4)
    response = client.put(
        "/api/profile",
        json={
            "days": 3,
            "budget": 3000,
            "proteins": ["any"],
            "goal": "home",
            "meal_types": ["breakfast", "lunch", "dinner"],
            "meals_per_day": 3,
            "persons": 2,
            "cooktime": "medium",
            "dietary_constraints": [],
            "store": "any",
            "expected_revision": 1,
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "PROFILE_STALE"
    assert body["details"]["current_revision"] == 2
    assert "current_profile" in body["details"]
    assert "detail" not in body


def test_preview_required_envelope(client):
    response = client.post("/api/generate-menu", json={})
    assert response.status_code == 428
    body = response.json()
    assert body["code"] == "STRATEGY_PREVIEW_REQUIRED"
    assert body["message"]
    assert "detail" not in body


def test_profile_validation_field_errors(client):
    response = save_profile(client, expected_revision=0, proteins=[])
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "PROFILE_PROTEIN_REQUIRED"
    assert any(item["field"] == "profile.proteins" for item in body["field_errors"])


def test_conflict_not_found_envelope(client):
    save_profile(client, expected_revision=0, proteins=["fish"])
    preview = client.post("/api/strategy/preview", json={})
    token = preview.json()["preview_token"]
    response = client.post(
        "/api/strategy/resolve-conflict",
        json={
            "preview_token": token,
            "conflict_id": "cfl_deadbeefdead",
            "action": "dismiss_memory_signal",
        },
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "CONFLICT_NOT_FOUND"
    assert "detail" not in body
