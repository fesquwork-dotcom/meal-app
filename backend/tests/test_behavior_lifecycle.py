"""Sprint 5.28 — snooze and revoke lifecycle tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from behavior.constants import (
    BEHAVIOR_RULES_VERSION,
    BehaviorInsightStatus,
    BehaviorInsightType,
    BehaviorSnoozeDuration,
)
from behavior.keys import compute_insight_key, new_insight_id
from behavior.lifecycle import behavior_insight_affects_strategy, compute_snoozed_until
from behavior.models import BehaviorInsightCandidate
from behavior.records import BehaviorInsightRecord
from behavior.repository import BehaviorRepository
from behavior.service import BehaviorService
from planning_preferences import PREFER_FAMILIAR_MEALS_RECOMMENDATION_KEY
from strategy.behavior_context import build_strategy_behavior_context
from strategy.builder import StrategyBuilder
from strategy.memory_context import StrategyMemoryContext
from tests.profile_test_helpers import save_profile

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "behavior-lifecycle.db"
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


def _seed(
    *,
    status: str,
    insight_type: BehaviorInsightType = BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT,
    target_key: str | None = "recipe-a",
    user_id: int = 42,
    recommendation_applied: bool = False,
) -> str:
    key = compute_insight_key(
        user_id=user_id,
        insight_type=insight_type,
        target_key=target_key,
    )
    insight_id = new_insight_id()
    record = BehaviorInsightRecord(
        id=insight_id,
        user_id=user_id,
        insight_key=key,
        insight_type=insight_type.value,
        target_key=target_key,
        target_label="label" if target_key else None,
        status=status,
        confidence=1.0 if status == BehaviorInsightStatus.CONFIRMED.value else 0.6,
        evidence_count=3,
        evidence_window_days=90,
        rule_version=BEHAVIOR_RULES_VERSION,
        first_seen_at=NOW_ISO,
        last_seen_at=NOW_ISO,
        created_at=NOW_ISO,
        updated_at=NOW_ISO,
        confirmed_at=NOW_ISO if status == BehaviorInsightStatus.CONFIRMED.value else None,
        dismissed_at=None,
        expires_at=(NOW + timedelta(days=180)).isoformat(),
        recommendation_applied_at=NOW_ISO if recommendation_applied else None,
        recommendation_key=(
            PREFER_FAMILIAR_MEALS_RECOMMENDATION_KEY if recommendation_applied else None
        ),
    )
    asyncio.run(BehaviorRepository()._insert(record))
    return insight_id


# --- Migration ---


def test_lifecycle_columns_added(client, tmp_path, monkeypatch):
    path = config.DATABASE_PATH

    async def _columns():
        async with aiosqlite.connect(path) as db:
            cursor = await db.execute("PRAGMA table_info(behavior_insights)")
            rows = await cursor.fetchall()
            await cursor.close()
        return {row[1] for row in rows}

    cols = asyncio.run(_columns())
    assert "snoozed_at" in cols
    assert "snoozed_until" in cols
    assert "revoked_at" in cols


# --- Snooze ---


def test_snooze_candidate_success(client):
    insight_id = _seed(status=BehaviorInsightStatus.CANDIDATE.value)
    response = client.post(
        f"/api/behavior/insights/{insight_id}/snooze",
        json={"duration": "7_days"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["insight"]["status"] == "snoozed"
    assert body["insight"]["snoozed_until"] is not None
    listed = client.get("/api/behavior/insights").json()["insights"]
    assert all(item["id"] != insight_id for item in listed)


def test_snooze_thirty_days(client):
    insight_id = _seed(status=BehaviorInsightStatus.CANDIDATE.value)
    response = client.post(
        f"/api/behavior/insights/{insight_id}/snooze",
        json={"duration": "30_days"},
    )
    assert response.status_code == 200
    until = response.json()["insight"]["snoozed_until"]
    expected = compute_snoozed_until(datetime.now(timezone.utc), BehaviorSnoozeDuration.THIRTY_DAYS)
    # Allow clock skew of a few seconds around request time.
    parsed = datetime.fromisoformat(until)
    assert abs((parsed - expected).total_seconds()) < 5


def test_snooze_confirmed_rejected(client):
    insight_id = _seed(status=BehaviorInsightStatus.CONFIRMED.value)
    response = client.post(
        f"/api/behavior/insights/{insight_id}/snooze",
        json={"duration": "7_days"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "BEHAVIOR_INSIGHT_NOT_SNOOZABLE"


def test_snooze_invalid_duration(client):
    insight_id = _seed(status=BehaviorInsightStatus.CANDIDATE.value)
    response = client.post(
        f"/api/behavior/insights/{insight_id}/snooze",
        json={"duration": "14_days"},
    )
    assert response.status_code == 422


def test_snooze_extra_fields_rejected(client):
    insight_id = _seed(status=BehaviorInsightStatus.CANDIDATE.value)
    response = client.post(
        f"/api/behavior/insights/{insight_id}/snooze",
        json={"duration": "7_days", "until": "2099-01-01"},
    )
    assert response.status_code == 422


def test_snooze_preserves_evidence_until_expiry(client):
    insight_id = _seed(status=BehaviorInsightStatus.CANDIDATE.value)
    repo = BehaviorRepository()
    snoozed = asyncio.run(
        repo.snooze(42, insight_id, duration=BehaviorSnoozeDuration.SEVEN_DAYS, now=NOW)
    )
    candidate = BehaviorInsightCandidate(
        insight_type=BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT,
        target_key="recipe-a",
        target_label="label",
        status=BehaviorInsightStatus.CANDIDATE,
        confidence=0.8,
        evidence_count=5,
        evidence_window_days=90,
        first_seen_at=NOW_ISO,
        last_seen_at=(NOW + timedelta(hours=1)).isoformat(),
    )
    updated, _, _ = asyncio.run(
        repo.upsert_insight(
            42, candidate, existing=snoozed, now=NOW + timedelta(hours=1)
        )
    )
    assert updated.status == BehaviorInsightStatus.SNOOZED.value
    assert updated.evidence_count == 5
    assert updated.snoozed_until == snoozed.snoozed_until

    later = NOW + timedelta(days=8)
    reopened, _, _ = asyncio.run(
        repo.upsert_insight(42, candidate, existing=updated, now=later)
    )
    assert reopened.status == BehaviorInsightStatus.CANDIDATE.value
    assert reopened.snoozed_until is None


def test_revoke_confirmed_success(client):
    insight_id = _seed(status=BehaviorInsightStatus.CONFIRMED.value)
    response = client.post(f"/api/behavior/insights/{insight_id}/revoke")
    assert response.status_code == 200
    body = response.json()
    assert body["insight"]["status"] == "revoked"
    assert body["insight"]["revoked_at"] is not None
    assert body["strategy_effect_changed"] is False
    assert body["profile_preference_remains_active"] is False
    listed = client.get("/api/behavior/insights").json()["insights"]
    assert all(item["id"] != insight_id for item in listed)


def test_revoke_availability_strategy_effect(client):
    insight_id = _seed(
        status=BehaviorInsightStatus.CONFIRMED.value,
        insight_type=BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION,
        target_key="milk",
    )
    response = client.post(f"/api/behavior/insights/{insight_id}/revoke")
    assert response.status_code == 200
    body = response.json()
    assert body["strategy_effect_changed"] is True

    confirmed = asyncio.run(BehaviorRepository().list_confirmed_insights(42))
    assert confirmed == []
    context = build_strategy_behavior_context(confirmed)
    result = StrategyBuilder().build_with_reasons({}, StrategyMemoryContext.empty(), context)
    assert "milk" not in result.strategy.availability_avoid_products


def test_revoke_idempotent(client):
    insight_id = _seed(status=BehaviorInsightStatus.CONFIRMED.value)
    first = client.post(f"/api/behavior/insights/{insight_id}/revoke")
    second = client.post(f"/api/behavior/insights/{insight_id}/revoke")
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["insight"]["status"] == "revoked"


def test_revoke_candidate_rejected(client):
    insight_id = _seed(status=BehaviorInsightStatus.CANDIDATE.value)
    response = client.post(f"/api/behavior/insights/{insight_id}/revoke")
    assert response.status_code == 409
    assert response.json()["code"] == "BEHAVIOR_INSIGHT_NOT_REVOKABLE"


def test_revoke_high_rate_preserves_profile_preference(client):
    _ensure_profile(client, planning_preferences={"prefer_familiar_meals": True})
    insight_id = _seed(
        status=BehaviorInsightStatus.CONFIRMED.value,
        insight_type=BehaviorInsightType.HIGH_REPLACEMENT_RATE,
        target_key=None,
        recommendation_applied=True,
    )
    revision_before = client.get("/api/profile").json()["revision"]
    response = client.post(f"/api/behavior/insights/{insight_id}/revoke")
    assert response.status_code == 200
    body = response.json()
    assert body["profile_preference_remains_active"] is True
    assert body["strategy_effect_changed"] is False

    profile = client.get("/api/profile").json()
    assert profile["revision"] == revision_before
    assert profile["profile"]["planning_preferences"]["prefer_familiar_meals"] is True


def test_revoke_before_recommendation_blocks_apply(client):
    _ensure_profile(client)
    insight_id = _seed(
        status=BehaviorInsightStatus.CONFIRMED.value,
        insight_type=BehaviorInsightType.HIGH_REPLACEMENT_RATE,
        target_key=None,
    )
    revoke = client.post(f"/api/behavior/insights/{insight_id}/revoke")
    assert revoke.status_code == 200
    revision = client.get("/api/profile").json()["revision"]
    apply = client.post(
        f"/api/behavior/insights/{insight_id}/apply-recommendation",
        json={"expected_profile_revision": revision},
    )
    assert apply.status_code == 409
    assert apply.json()["code"] == "BEHAVIOR_RECOMMENDATION_NOT_AVAILABLE"


def test_revoked_not_reopened_by_evaluation(client):
    insight_id = _seed(
        status=BehaviorInsightStatus.CONFIRMED.value,
        insight_type=BehaviorInsightType.HIGH_REPLACEMENT_RATE,
        target_key=None,
    )
    repo = BehaviorRepository()
    revoked = asyncio.run(repo.revoke(42, insight_id, now=NOW))
    candidate = BehaviorInsightCandidate(
        insight_type=BehaviorInsightType.HIGH_REPLACEMENT_RATE,
        target_key=None,
        target_label=None,
        status=BehaviorInsightStatus.CANDIDATE,
        confidence=0.9,
        evidence_count=8,
        evidence_window_days=90,
        first_seen_at=NOW_ISO,
        last_seen_at=NOW_ISO,
    )
    updated, _, _ = asyncio.run(
        repo.upsert_insight(
            42, candidate, existing=revoked, now=NOW + timedelta(days=1)
        )
    )
    assert updated.status == BehaviorInsightStatus.REVOKED.value


def test_capabilities_on_list(client):
    cand = _seed(status=BehaviorInsightStatus.CANDIDATE.value, target_key="r1")
    conf = _seed(
        status=BehaviorInsightStatus.CONFIRMED.value,
        insight_type=BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION,
        target_key="milk",
    )
    insights = {item["id"]: item for item in client.get("/api/behavior/insights").json()["insights"]}
    assert insights[cand]["can_snooze"] is True
    assert insights[cand]["can_revoke"] is False
    assert insights[cand]["can_confirm"] is True
    assert insights[conf]["can_revoke"] is True
    assert insights[conf]["can_snooze"] is False


def test_strategy_effect_helper():
    assert behavior_insight_affects_strategy(
        BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION
    )
    assert not behavior_insight_affects_strategy(BehaviorInsightType.HIGH_REPLACEMENT_RATE)
    assert not behavior_insight_affects_strategy(
        BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT
    )


def test_foreign_snooze_404(client):
    response = client.post(
        "/api/behavior/insights/missing/snooze",
        json={"duration": "7_days"},
    )
    assert response.status_code == 404
