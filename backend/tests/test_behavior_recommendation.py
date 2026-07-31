"""Tests for behavior recommendation apply action (Sprint 5.27)."""

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
from planning_preferences import PREFER_FAMILIAR_MEALS_RECOMMENDATION_KEY
from tests.profile_test_helpers import save_profile

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "behavior-recommendation.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _ensure_profile(client, revision: int = 0, **overrides):
    response = save_profile(client, expected_revision=revision, **overrides)
    assert response.status_code == 200, response.text
    return response.json()


def _profile_revision(client) -> int:
    return client.get("/api/profile").json()["revision"]


def _seed_confirmed_high_rate(*, user_id: int = 42, applied: bool = False) -> str:
    key = compute_insight_key(
        user_id=user_id,
        insight_type=BehaviorInsightType.HIGH_REPLACEMENT_RATE,
        target_key=None,
    )
    insight_id = new_insight_id()
    record = BehaviorInsightRecord(
        id=insight_id,
        user_id=user_id,
        insight_key=key,
        insight_type=BehaviorInsightType.HIGH_REPLACEMENT_RATE.value,
        target_key=None,
        target_label=None,
        status=BehaviorInsightStatus.CONFIRMED.value,
        confidence=1.0,
        evidence_count=5,
        evidence_window_days=90,
        rule_version=BEHAVIOR_RULES_VERSION,
        first_seen_at=NOW_ISO,
        last_seen_at=NOW_ISO,
        created_at=NOW_ISO,
        updated_at=NOW_ISO,
        confirmed_at=NOW_ISO,
        dismissed_at=None,
        expires_at=(NOW + timedelta(days=180)).isoformat(),
        recommendation_applied_at=NOW_ISO if applied else None,
        recommendation_key=PREFER_FAMILIAR_MEALS_RECOMMENDATION_KEY if applied else None,
    )
    asyncio.run(BehaviorRepository()._insert(record))
    return insight_id


def _apply(client, insight_id: str, expected_revision: int):
    return client.post(
        f"/api/behavior/insights/{insight_id}/apply-recommendation",
        json={"expected_profile_revision": expected_revision},
    )


def test_confirmed_high_rate_can_apply_recommendation(client):
    _ensure_profile(client)
    insight_id = _seed_confirmed_high_rate()
    revision = _profile_revision(client)

    response = _apply(client, insight_id, revision)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "applied"
    assert body["recommendation_key"] == PREFER_FAMILIAR_MEALS_RECOMMENDATION_KEY
    assert body["profile_revision"] == revision + 1
    assert body["profile"]["planning_preferences"]["prefer_familiar_meals"] is True

    insight = client.get("/api/behavior/insights").json()["insights"][0]
    assert insight["recommendation"]["applied"] is True
    assert insight["recommendation"]["can_apply"] is False


def test_candidate_rejected(client):
    _ensure_profile(client)
    key = compute_insight_key(
        user_id=42,
        insight_type=BehaviorInsightType.HIGH_REPLACEMENT_RATE,
        target_key=None,
    )
    insight_id = new_insight_id()
    record = BehaviorInsightRecord(
        id=insight_id,
        user_id=42,
        insight_key=key,
        insight_type=BehaviorInsightType.HIGH_REPLACEMENT_RATE.value,
        target_key=None,
        target_label=None,
        status=BehaviorInsightStatus.CANDIDATE.value,
        confidence=0.8,
        evidence_count=5,
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
    revision = _profile_revision(client)

    response = _apply(client, insight_id, revision)
    assert response.status_code == 409
    assert response.json()["code"] == "BEHAVIOR_RECOMMENDATION_NOT_AVAILABLE"


def test_availability_insight_unsupported(client):
    _ensure_profile(client)
    key = compute_insight_key(
        user_id=42,
        insight_type=BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION,
        target_key="milk",
    )
    insight_id = new_insight_id()
    record = BehaviorInsightRecord(
        id=insight_id,
        user_id=42,
        insight_key=key,
        insight_type=BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION.value,
        target_key="milk",
        target_label="молоко",
        status=BehaviorInsightStatus.CONFIRMED.value,
        confidence=1.0,
        evidence_count=3,
        evidence_window_days=90,
        rule_version=BEHAVIOR_RULES_VERSION,
        first_seen_at=NOW_ISO,
        last_seen_at=NOW_ISO,
        created_at=NOW_ISO,
        updated_at=NOW_ISO,
        confirmed_at=NOW_ISO,
        dismissed_at=None,
        expires_at=(NOW + timedelta(days=180)).isoformat(),
    )
    asyncio.run(BehaviorRepository()._insert(record))
    revision = _profile_revision(client)

    response = _apply(client, insight_id, revision)
    assert response.status_code == 409
    assert response.json()["code"] == "BEHAVIOR_RECOMMENDATION_NOT_AVAILABLE"


def test_profile_already_true_is_already_covered(client):
    _ensure_profile(
        client,
        planning_preferences={"prefer_familiar_meals": True},
    )
    insight_id = _seed_confirmed_high_rate()
    revision = _profile_revision(client)

    response = _apply(client, insight_id, revision)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "already_covered"
    assert body["profile_revision"] == revision


def test_profile_false_overrides_to_true(client):
    _ensure_profile(
        client,
        planning_preferences={"prefer_familiar_meals": False},
    )
    insight_id = _seed_confirmed_high_rate()
    revision = _profile_revision(client)

    response = _apply(client, insight_id, revision)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "applied"
    assert body["profile"]["planning_preferences"]["prefer_familiar_meals"] is True
    assert body["profile_revision"] == revision + 1


def test_repeat_apply_is_idempotent(client):
    _ensure_profile(client)
    insight_id = _seed_confirmed_high_rate()
    revision = _profile_revision(client)

    first = _apply(client, insight_id, revision)
    assert first.status_code == 200
    assert first.json()["status"] == "applied"

    second = _apply(client, insight_id, first.json()["profile_revision"])
    assert second.status_code == 200
    body = second.json()
    assert body["status"] == "already_applied"
    assert body["profile_revision"] == first.json()["profile_revision"]


def test_stale_profile_revision_rejected(client):
    _ensure_profile(client)
    insight_id = _seed_confirmed_high_rate()
    revision = _profile_revision(client)

    response = _apply(client, insight_id, revision - 1)
    assert response.status_code == 409
    assert response.json()["code"] == "BEHAVIOR_RECOMMENDATION_PROFILE_STALE"


def test_foreign_insight_returns_404(client):
    _ensure_profile(client)
    revision = _profile_revision(client)

    response = _apply(client, "missing-id", revision)
    assert response.status_code == 404
    assert response.json()["code"] == "BEHAVIOR_INSIGHT_NOT_FOUND"


def test_request_rejects_extra_fields(client):
    _ensure_profile(client)
    insight_id = _seed_confirmed_high_rate()
    revision = _profile_revision(client)

    response = client.post(
        f"/api/behavior/insights/{insight_id}/apply-recommendation",
        json={
            "expected_profile_revision": revision,
            "prefer_familiar_meals": True,
        },
    )
    assert response.status_code == 422
