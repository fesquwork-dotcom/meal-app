"""Decision Learning HTTP contract."""

import asyncio
from datetime import datetime, timezone

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from learning_test_helpers import seed_learning_candidate


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "learning-api.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def test_list_materializes_candidate_and_is_idempotent(client):
    seed_learning_candidate(client)
    first = client.get("/api/learning/recommendations")
    second = client.get("/api/learning/recommendations")
    assert first.status_code == second.status_code == 200
    assert first.json()["candidate_count"] == 1
    assert len(first.json()["recommendations"]) == 1
    assert (
        first.json()["recommendations"][0]["recommendation_id"]
        == second.json()["recommendations"][0]["recommendation_id"]
    )


def test_empty_when_no_finalized_outcomes(client):
    response = client.get("/api/learning/recommendations")
    assert response.status_code == 200
    assert response.json()["recommendations"] == []


def test_unknown_actions_are_404(client):
    for action in ("accept", "dismiss"):
        response = client.post(
            f"/api/learning/recommendations/unknown/{action}"
        )
        assert response.status_code == 404
        assert (
            response.json()["code"]
            == "LEARNING_RECOMMENDATION_NOT_FOUND"
        )


def test_get_does_not_expose_history_rows(client):
    seed_learning_candidate(client)
    item = client.get("/api/learning/recommendations").json()[
        "recommendations"
    ][0]
    client.post(
        f"/api/learning/recommendations/{item['recommendation_id']}/dismiss"
    )
    response = client.get("/api/learning/recommendations")
    assert response.status_code == 200
    assert response.json()["recommendations"] == []


def test_behavior_high_replacement_candidate_suppresses_duplicate(client):
    seed_learning_candidate(client)
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    async def insert_behavior_duplicate():
        async with aiosqlite.connect(database.resolve_database_path()) as db:
            await db.execute(
                """
                INSERT INTO behavior_insights (
                    id, user_id, insight_key, insight_type, target_key,
                    target_label, status, confidence, evidence_count,
                    evidence_window_days, rule_version, first_seen_at,
                    last_seen_at, created_at, updated_at, confirmed_at,
                    dismissed_at, expires_at
                ) VALUES (?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
                """,
                (
                    "behavior-duplicate",
                    42,
                    "behavior:high-replacement",
                    "high_replacement_rate",
                    "candidate",
                    0.8,
                    9,
                    90,
                    1,
                    now,
                    now,
                    now,
                    now,
                    "2099-01-01T00:00:00+00:00",
                ),
            )
            await db.commit()

    asyncio.run(insert_behavior_duplicate())
    response = client.get("/api/learning/recommendations")
    assert response.status_code == 200
    assert response.json()["recommendations"] == []
