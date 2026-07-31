"""API contract for /api/learned-preferences (list/accept/revoke)."""

import asyncio

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from learned_preferences.repository import preference_key

FAMILIAR_ID = preference_key("prefer_familiar_meals")


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "lp-api.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    monkeypatch.setattr(config, "ADAPTIVE_PREFERENCES", False)
    asyncio.run(database.init_db())


@pytest.fixture
def client():
    return TestClient(main.app)


def _seed_accepted_recommendation():
    async def _run():
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_learning_recommendations_table(db)
            await db.execute(
                """
                INSERT INTO learning_recommendations (
                    id, user_id, recommendation_key, recommendation_type,
                    decision_key, status, confidence, rule_version,
                    source_strategy_id, profile_patch_json,
                    created_at, updated_at, accepted_at, dismissed_at, expired_at
                ) VALUES (?, 42, ?, ?, ?, 'accepted', 'strong', 1, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    "rec-familiar",
                    "v1:profile_enable_prefer_familiar_meals",
                    "profile_enable_prefer_familiar_meals",
                    "planning.prefer_familiar_meals",
                    "s1",
                    '{"planning_preferences": {"prefer_familiar_meals": true}}',
                    "2026-07-10T00:00:00+00:00",
                    "2026-07-10T00:00:00+00:00",
                    "2026-07-11T00:00:00+00:00",
                ),
            )
            await db.commit()

    asyncio.run(_run())


def test_empty_without_accepted_recommendations(client):
    response = client.get("/api/learned-preferences")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["preferences"] == []


def test_list_returns_candidate_from_accepted_recommendation(client):
    _seed_accepted_recommendation()
    body = client.get("/api/learned-preferences").json()
    assert len(body["preferences"]) == 1
    candidate = body["preferences"][0]
    assert candidate["id"] == FAMILIAR_ID
    assert candidate["type"] == "prefer_familiar_meals"
    assert candidate["status"] == "candidate"
    assert candidate["title"]
    assert candidate["summary"]
    assert candidate["evidence"]["source"] == "decision_learning"


def test_accept_then_revoke_flow(client):
    _seed_accepted_recommendation()
    accepted = client.post(
        f"/api/learned-preferences/{FAMILIAR_ID}/accept"
    ).json()
    assert accepted["preferences"][0]["status"] == "active"
    assert accepted["preferences"][0]["accepted_at"]
    assert accepted["preferences"][0]["planning_effect"] == "disabled"

    listed = client.get("/api/learned-preferences").json()
    assert listed["preferences"][0]["status"] == "active"

    revoked = client.post(
        f"/api/learned-preferences/{FAMILIAR_ID}/revoke"
    ).json()
    assert revoked["preferences"][0]["status"] == "revoked"


def test_accept_unknown_preference_returns_404(client):
    response = client.post("/api/learned-preferences/v1:stable_cook_days/accept")
    assert response.status_code == 404
    assert response.json()["code"] == "LEARNED_PREFERENCE_NOT_FOUND"


def test_endpoints_require_auth(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    unauth = TestClient(main.app)
    assert unauth.get("/api/learned-preferences").status_code == 401
    assert (
        unauth.post("/api/learned-preferences/v1:prefer_fast_meals/accept").status_code
        == 401
    )


def test_feature_flag_default_false_does_not_block_api(client):
    # DoD: the flag gates planning influence, not the read/write API itself.
    assert config.ADAPTIVE_PREFERENCES is False
    _seed_accepted_recommendation()
    assert client.get("/api/learned-preferences").status_code == 200
    assert (
        client.post(f"/api/learned-preferences/{FAMILIAR_ID}/accept").status_code == 200
    )


def test_active_preference_reports_applied_only_when_flag_enabled(
    client, monkeypatch
):
    _seed_accepted_recommendation()
    client.post(f"/api/learned-preferences/{FAMILIAR_ID}/accept")
    monkeypatch.setattr(config, "ADAPTIVE_PREFERENCES", True)
    listed = client.get("/api/learned-preferences").json()
    assert listed["preferences"][0]["status"] == "active"
    assert listed["preferences"][0]["planning_effect"] == "applied"
