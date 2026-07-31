"""API / service wiring for Learned Preference effectiveness."""

from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from learned_preferences.effectiveness_models import (
    LearnedPreferencePlanObservation,
)
from learned_preferences.effectiveness_service import (
    LearnedPreferenceEffectivenessService,
)
from learned_preferences.observation_repository import (
    LearnedPreferenceObservationRepository,
)
from learned_preferences.repository import LearnedPreferenceRepository
from strategy.applied_learned_preferences import (
    AppliedLearnedPreferenceDecision,
    AppliedLearnedPreferencesSnapshot,
)
from strategy.builder import StrategyBuilder
from strategy.repository import StrategyRepository
from tests.strategy_fixtures import build_test_profile


@pytest.fixture(autouse=True)
def _init_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "lp-eff.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    monkeypatch.setattr(config, "ADAPTIVE_PREFERENCES", True)
    asyncio.run(database.init_db())


@pytest.fixture
def client():
    return TestClient(main.app)


def _applied_snapshot(preference_type: str = "prefer_familiar_meals"):
    decision_key = (
        "planning.prefer_familiar_meals"
        if preference_type == "prefer_familiar_meals"
        else "cooking.prefer_faster"
    )
    reason = (
        "LEARNED_FAMILIAR_MEALS_APPLIED"
        if preference_type == "prefer_familiar_meals"
        else "LEARNED_FASTER_MEALS_APPLIED"
    )
    return AppliedLearnedPreferencesSnapshot(
        enabled=True,
        decisions=[
            AppliedLearnedPreferenceDecision(
                preference_type=preference_type,  # type: ignore[arg-type]
                applied=True,
                reason_code=reason,  # type: ignore[arg-type]
                decision_key=decision_key,  # type: ignore[arg-type]
            )
        ],
    )


def _save_finalized(
    *,
    day_offset: int,
    preference_type: str = "prefer_familiar_meals",
    with_snapshot: bool = True,
    status: str = "completed",
):
    strategy = StrategyBuilder().build(build_test_profile(days=3))
    plan_start = date.today() - timedelta(days=21 + day_offset * 7)
    strategy_id = asyncio.run(
        StrategyRepository().save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=plan_start,
            applied_learned_preferences=(
                _applied_snapshot(preference_type) if with_snapshot else None
            ),
        )
    )
    async def _finalize():
        db_path = database.resolve_database_path()
        import aiosqlite

        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                UPDATE weekly_strategies
                SET status = ?, completed_at = updated_at
                WHERE id = ?
                """,
                (status, strategy_id),
            )
            await db.commit()

    asyncio.run(_finalize())
    return strategy_id, plan_start


def _activate_preference(preference_type: str = "prefer_familiar_meals"):
    pref_id = f"v1:{preference_type}"
    asyncio.run(
        LearnedPreferenceRepository().create(
            user_id=42,
            preference_id=pref_id,
            preference_type=preference_type,
            source="decision_learning",
            evidence_json=json.dumps(
                {"source": "decision_learning", "confidence": "strong"}
            ),
            preference_json=json.dumps({"type": preference_type}),
            status="active",
        )
    )
    return pref_id


def test_candidate_has_null_effectiveness(client):
    async def _seed():
        import aiosqlite

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
                    "rec-familiar-eff",
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

    asyncio.run(_seed())
    body = client.get("/api/learned-preferences").json()
    assert body["preferences"]
    candidate = body["preferences"][0]
    assert candidate["status"] == "candidate"
    assert candidate["effectiveness"] is None


def test_list_includes_effectiveness_for_active(client):
    _activate_preference()
    for i in range(4):
        _save_finalized(day_offset=i)
    body = client.get("/api/learned-preferences").json()
    pref = body["preferences"][0]
    assert pref["effectiveness"] is not None
    assert pref["effectiveness"]["status"] in {
        "insufficient_data",
        "emerging",
        "effective",
        "neutral",
        "ineffective",
    }
    assert "title" in pref["effectiveness"]
    assert "evidence_text" in pref["effectiveness"]


def test_observation_repo_excludes_legacy_and_active_current():
    _save_finalized(day_offset=0, with_snapshot=False)
    _save_finalized(day_offset=1, with_snapshot=True)
    # Active current plan with applied snapshot must not count.
    strategy = StrategyBuilder().build(build_test_profile(days=3))
    asyncio.run(
        StrategyRepository().save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=date.today(),
            applied_learned_preferences=_applied_snapshot(),
        )
    )
    observations = asyncio.run(
        LearnedPreferenceObservationRepository().load_applied_plan_observations(
            42, "prefer_familiar_meals"
        )
    )
    assert len(observations) == 1
    assert all(item.preference_applied for item in observations)


def test_effectiveness_service_failure_does_not_break_list(client, monkeypatch):
    _activate_preference()

    async def boom(*_args, **_kwargs):
        raise RuntimeError("effectiveness down")

    monkeypatch.setattr(
        main._learned_preference_service._effectiveness,
        "get_all_effectiveness",
        boom,
    )
    response = client.get("/api/learned-preferences")
    assert response.status_code == 200
    pref = response.json()["preferences"][0]
    assert pref["status"] == "active"
    assert pref["effectiveness"] is None


def test_service_returns_response_for_evaluable_type():
    service = LearnedPreferenceEffectivenessService()

    class FakeRepo:
        async def load_applied_plan_observations(self, *_args, **_kwargs):
            return [
                LearnedPreferencePlanObservation(
                    plan_date=date(2026, 1, 1) + timedelta(days=i * 7),
                    preference_applied=True,
                    replacement_count=0,
                    planned_meal_count=10,
                    meal_suited_count=3,
                    meal_cooked_count=0,
                    plan_completed=True,
                    decision_outcome="successful",
                )
                for i in range(4)
            ]

    service = LearnedPreferenceEffectivenessService(
        observation_repository=FakeRepo()  # type: ignore[arg-type]
    )
    payload = asyncio.run(service.get_effectiveness(42, "prefer_familiar_meals"))
    assert payload is not None
    assert payload.status == "effective"
