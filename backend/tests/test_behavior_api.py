"""API tests for behavior insight endpoints."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from behavior.constants import (
    BEHAVIOR_RULES_VERSION,
    BehaviorInsightStatus,
    BehaviorInsightType,
)
from behavior.keys import compute_insight_key, new_insight_id
from behavior.records import BehaviorInsightRecord
from behavior.repository import BehaviorRepository
from memory.records import MemoryEventRecord
from memory.repository import MemoryRepository

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "behavior-api.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _seed_candidate(*, user_id: int = 42, target_key: str = "recipe-a") -> str:
    key = compute_insight_key(
        user_id=user_id,
        insight_type=BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT,
        target_key=target_key,
    )
    insight_id = new_insight_id()
    record = BehaviorInsightRecord(
        id=insight_id,
        user_id=user_id,
        insight_key=key,
        insight_type=BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT.value,
        target_key=target_key,
        target_label=None,
        status=BehaviorInsightStatus.CANDIDATE.value,
        confidence=0.6,
        evidence_count=2,
        evidence_window_days=90,
        rule_version=BEHAVIOR_RULES_VERSION,
        first_seen_at=NOW_ISO,
        last_seen_at=NOW_ISO,
        created_at=NOW_ISO,
        updated_at=NOW_ISO,
        confirmed_at=None,
        dismissed_at=None,
        expires_at=(NOW + timedelta(days=180)).isoformat(),
    )
    asyncio.run(BehaviorRepository()._insert(record))
    return insight_id


def _seed_from_events():
    repo = MemoryRepository()
    for index in range(2):
        asyncio.run(
            repo.insert_event(
                MemoryEventRecord(
                    id=f"evt-{index}",
                    user_id=42,
                    event_type="meal_replaced",
                    event_key=f"k-{index}",
                    strategy_id="s1",
                    meal_id="day1_lunch",
                    recipe_id="recipe-a",
                    reason_code="generic",
                    target_type=None,
                    target_value=None,
                    target_label=None,
                    metadata_json=None,
                    created_at=NOW_ISO,
                )
            )
        )


def test_list_requires_auth(client, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    assert client.get("/api/behavior/insights").status_code == 401


def test_list_returns_candidate(client):
    _seed_from_events()
    response = client.get("/api/behavior/insights")
    assert response.status_code == 200
    body = response.json()
    assert body["candidate_count"] == 1
    insight = body["insights"][0]
    assert insight["status"] == "candidate"
    assert insight["can_confirm"] is True
    assert "recipe-a" not in insight["title"]
    assert "insight_key" not in insight
    assert "target_key" not in insight
    assert "user_id" not in insight


def test_list_returns_confirmed(client):
    insight_id = _seed_candidate()
    client.post(f"/api/behavior/insights/{insight_id}/confirm")
    body = client.get("/api/behavior/insights").json()
    assert body["confirmed_count"] == 1
    assert body["insights"][0]["status"] == "confirmed"


def test_list_empty(client):
    body = client.get("/api/behavior/insights").json()
    assert body == {"insights": [], "candidate_count": 0, "confirmed_count": 0}


def test_foreign_insight_not_visible(client, monkeypatch):
    foreign_id = _seed_candidate(user_id=99, target_key="recipe-foreign")
    body = client.get("/api/behavior/insights").json()
    assert all(item["id"] != foreign_id for item in body["insights"])
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)
    assert client.post(f"/api/behavior/insights/{foreign_id}/confirm").status_code == 200


def test_confirm_candidate(client):
    insight_id = _seed_candidate()
    response = client.post(f"/api/behavior/insights/{insight_id}/confirm")
    assert response.status_code == 200
    insight = response.json()["insight"]
    assert insight["status"] == "confirmed"
    assert insight["confidence"] == 1.0
    assert insight["can_confirm"] is False


def test_confirm_idempotent(client):
    insight_id = _seed_candidate()
    client.post(f"/api/behavior/insights/{insight_id}/confirm")
    again = client.post(f"/api/behavior/insights/{insight_id}/confirm")
    assert again.status_code == 200
    assert again.json()["insight"]["status"] == "confirmed"


def test_confirm_rejects_observed(client):
    key = compute_insight_key(
        user_id=42,
        insight_type=BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT,
        target_key="recipe-obs",
    )
    insight_id = new_insight_id()
    asyncio.run(
        BehaviorRepository()._insert(
            BehaviorInsightRecord(
                id=insight_id,
                user_id=42,
                insight_key=key,
                insight_type=BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT.value,
                target_key="recipe-obs",
                target_label=None,
                status=BehaviorInsightStatus.OBSERVED.value,
                confidence=0.35,
                evidence_count=1,
                evidence_window_days=90,
                rule_version=BEHAVIOR_RULES_VERSION,
                first_seen_at=NOW_ISO,
                last_seen_at=NOW_ISO,
                created_at=NOW_ISO,
                updated_at=NOW_ISO,
                confirmed_at=None,
                dismissed_at=None,
                expires_at=None,
            )
        )
    )
    response = client.post(f"/api/behavior/insights/{insight_id}/confirm")
    assert response.status_code == 409
    assert response.json()["code"] == "BEHAVIOR_INSIGHT_NOT_CONFIRMABLE"


def test_confirm_rejects_dismissed(client):
    insight_id = _seed_candidate(target_key="recipe-dismissed")
    client.post(f"/api/behavior/insights/{insight_id}/dismiss")
    response = client.post(f"/api/behavior/insights/{insight_id}/confirm")
    assert response.status_code == 409


def test_dismiss_candidate(client):
    insight_id = _seed_candidate()
    response = client.post(f"/api/behavior/insights/{insight_id}/dismiss")
    assert response.status_code == 200
    assert response.json()["insight"]["status"] == "dismissed"
    assert client.get("/api/behavior/insights").json()["insights"] == []


def test_dismiss_idempotent(client):
    insight_id = _seed_candidate(target_key="recipe-dup")
    client.post(f"/api/behavior/insights/{insight_id}/dismiss")
    again = client.post(f"/api/behavior/insights/{insight_id}/dismiss")
    assert again.status_code == 200
    assert again.json()["insight"]["status"] == "dismissed"


def test_dismiss_rejects_confirmed(client):
    insight_id = _seed_candidate(target_key="recipe-confirmed")
    client.post(f"/api/behavior/insights/{insight_id}/confirm")
    response = client.post(f"/api/behavior/insights/{insight_id}/dismiss")
    assert response.status_code == 409
    assert response.json()["code"] == "BEHAVIOR_INSIGHT_NOT_DISMISSIBLE"


def test_foreign_insight_confirm_404(client, monkeypatch):
    insight_id = _seed_candidate(user_id=99, target_key="recipe-x")
    assert client.post(f"/api/behavior/insights/{insight_id}/confirm").status_code == 404


def test_unknown_insight_404(client):
    response = client.post("/api/behavior/insights/missing/confirm")
    assert response.status_code == 404
    assert response.json()["code"] == "BEHAVIOR_INSIGHT_NOT_FOUND"


def test_expired_insight_not_listed(client):
    insight_id = _seed_candidate(target_key="recipe-expired")
    asyncio.run(
        BehaviorRepository().mark_expired(42, insight_id, now=NOW + timedelta(days=1))
    )
    body = client.get("/api/behavior/insights").json()
    assert body["insights"] == []


def test_confirm_then_dismiss_conflict(client):
    insight_id = _seed_candidate(target_key="recipe-seq")
    confirm = client.post(f"/api/behavior/insights/{insight_id}/confirm")
    dismiss = client.post(f"/api/behavior/insights/{insight_id}/dismiss")
    assert confirm.status_code == 200
    assert dismiss.status_code == 409


def test_dismiss_then_confirm_conflict(client):
    insight_id = _seed_candidate(target_key="recipe-seq2")
    dismiss = client.post(f"/api/behavior/insights/{insight_id}/dismiss")
    confirm = client.post(f"/api/behavior/insights/{insight_id}/confirm")
    assert dismiss.status_code == 200
    assert confirm.status_code == 409
