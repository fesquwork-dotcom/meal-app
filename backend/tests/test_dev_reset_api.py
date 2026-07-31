"""Sprint 9.5 — controlled reset API."""

from __future__ import annotations

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from learned_preferences.repository import LearnedPreferenceRepository


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "reset.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _seed_profile_and_preference():
    asyncio.run(database.save_profile(42, {
        "goal": "home",
        "days": 3,
        "budget": 3000.0,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "meals_per_day": 3,
        "proteins": ["any"],
        "cooktime": "medium",
        "allergies": "нет",
        "store": "any",
    }))
    asyncio.run(
        LearnedPreferenceRepository().create(
            user_id=42,
            preference_id="v1:prefer_familiar_meals",
            preference_type="prefer_familiar_meals",
            source="decision_learning",
            evidence_json=json.dumps(
                {"source": "decision_learning", "confidence": "strong"}
            ),
            preference_json=json.dumps({"type": "prefer_familiar_meals"}),
            status="active",
        )
    )


def test_reset_requires_confirm(client):
    response = client.post(
        "/api/dev/reset-current-user",
        json={"confirm": "YES", "mode": "history_only"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "DEV_RESET_CONFIRM_REQUIRED"


def test_history_only_keeps_profile(client):
    _seed_profile_and_preference()
    response = client.post(
        "/api/dev/reset-current-user",
        json={"confirm": "RESET", "mode": "history_only"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "history_only"
    assert body["deleted"]["learned_preferences"] >= 1
    profile = asyncio.run(database.get_profile(42))
    assert profile is not None


def test_full_user_removes_profile(client):
    _seed_profile_and_preference()
    response = client.post(
        "/api/dev/reset-current-user",
        json={"confirm": "RESET", "mode": "full_user"},
    )
    assert response.status_code == 200
    assert response.json()["deleted"].get("profiles", 0) >= 1
    assert asyncio.run(database.get_profile(42)) is None


def test_reset_only_targets_current_user(client):
    _seed_profile_and_preference()
    asyncio.run(database.save_profile(99, {
        "goal": "home",
        "days": 3,
        "budget": 3000.0,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "meals_per_day": 3,
        "proteins": ["any"],
        "cooktime": "medium",
        "allergies": "нет",
        "store": "any",
    }))
    client.post(
        "/api/dev/reset-current-user",
        json={"confirm": "RESET", "mode": "full_user"},
    )
    assert asyncio.run(database.get_profile(99)) is not None
    assert asyncio.run(database.get_profile(42)) is None
