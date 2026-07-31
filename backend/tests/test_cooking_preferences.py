"""Tests for cooking preferences model and persistence (Sprint 5.22)."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from cooking_preferences import (
    CookingPreferences,
    cooking_preferences_from_json,
    parse_cooking_preferences,
    serialize_cooking_preferences_json,
)
from strategy.fingerprint import compute_profile_hash
from tests.profile_test_helpers import save_profile


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "cooking-prefs.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def test_parse_absent_preference():
    assert parse_cooking_preferences({}).prefer_faster_meals is None


def test_round_trip_json():
    prefs = CookingPreferences(prefer_faster_meals=True)
    raw = serialize_cooking_preferences_json(prefs)
    assert raw is not None
    restored = cooking_preferences_from_json(raw)
    assert restored.prefer_faster_meals is True


def test_profile_hash_includes_cooking_preferences():
    base = {"goal": "home", "days": 5, "cooktime": "medium", "proteins": ["any"]}
    without = compute_profile_hash({**base, "cooking_preferences": None})
    with_pref = compute_profile_hash(
        {**base, "cooking_preferences": {"prefer_faster_meals": True}}
    )
    assert without != with_pref


def test_profile_put_round_trip(client):
    save_profile(client, expected_revision=0)
    response = save_profile(
        client,
        expected_revision=1,
        cooking_preferences={"prefer_faster_meals": True},
    )
    assert response.status_code == 200
    profile = response.json()["profile"]
    assert profile["cooking_preferences"]["prefer_faster_meals"] is True


def test_legacy_profile_without_field(client):
    save_profile(client, expected_revision=0)
    profile = client.get("/api/profile").json()["profile"]
    assert profile.get("cooking_preferences") is None
