"""Sprint 9.4 — review dismiss persistence and cohort re-show."""

from __future__ import annotations

import asyncio
import json
from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from learned_preferences.effectiveness import (
    effectiveness_generation,
    evaluate_learned_preference_effectiveness,
)
from learned_preferences.effectiveness_models import (
    REVIEW_COHORT_SIZE,
    LearnedPreferencePlanObservation,
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
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "lp-review.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    monkeypatch.setattr(config, "ADAPTIVE_PREFERENCES", True)
    asyncio.run(database.init_db())


@pytest.fixture
def client():
    return TestClient(main.app)


def _obs(i: int, *, negative: bool = True):
    if negative:
        return LearnedPreferencePlanObservation(
            plan_date=date(2026, 1, 1) + timedelta(days=i * 7),
            preference_applied=True,
            replacement_count=5,
            planned_meal_count=10,
            meal_suited_count=0,
            meal_cooked_count=0,
            plan_completed=False,
            decision_outcome="unsuccessful",
        )
    return LearnedPreferencePlanObservation(
        plan_date=date(2026, 1, 1) + timedelta(days=i * 7),
        preference_applied=True,
        replacement_count=0,
        planned_meal_count=10,
        meal_suited_count=3,
        meal_cooked_count=0,
        plan_completed=True,
        decision_outcome="successful",
    )


def test_effectiveness_generation_cohorts():
    assert REVIEW_COHORT_SIZE == 4
    assert effectiveness_generation(0) == 0
    assert effectiveness_generation(3) == 0
    assert effectiveness_generation(4) == 1
    assert effectiveness_generation(7) == 1
    assert effectiveness_generation(8) == 2
    assert effectiveness_generation(12) == 3
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals", [_obs(i) for i in range(4)]
    )
    assert result.generation == 1
    assert result.status == "ineffective"


def _activate():
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


def _applied_snapshot():
    return AppliedLearnedPreferencesSnapshot(
        enabled=True,
        decisions=[
            AppliedLearnedPreferenceDecision(
                preference_type="prefer_familiar_meals",
                applied=True,
                reason_code="LEARNED_FAMILIAR_MEALS_APPLIED",
                decision_key="planning.prefer_familiar_meals",
            )
        ],
    )


def _save_finalized(day_offset: int):
    strategy = StrategyBuilder().build(build_test_profile(days=3))
    plan_start = date.today() - timedelta(days=21 + day_offset * 7)
    strategy_id = asyncio.run(
        StrategyRepository().save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=plan_start,
            applied_learned_preferences=_applied_snapshot(),
        )
    )

    async def _finalize():
        import aiosqlite
        import uuid

        async with aiosqlite.connect(database.resolve_database_path()) as db:
            await db.execute(
                """
                UPDATE weekly_strategies
                SET status = 'completed',
                    completed_at = updated_at,
                    decision_outcomes_json = ?
                WHERE id = ?
                """,
                (
                    json.dumps(
                        {
                            "version": 1,
                            "outcomes": [
                                {
                                    "decision_key": "planning.prefer_familiar_meals",
                                    "result": "high_replacement",
                                    "confidence": "strong",
                                    "evidence_count": 5,
                                    "status": "unsuccessful",
                                }
                            ],
                            "feedback": [],
                        }
                    ),
                    strategy_id,
                ),
            )
            for meal_i in range(5):
                await db.execute(
                    """
                    INSERT INTO memory_events (
                        id, user_id, event_type, event_key, strategy_id, meal_id,
                        created_at
                    ) VALUES (?, 42, 'meal_replaced', ?, ?, ?, ?)
                    """,
                    (
                        str(uuid.uuid4()),
                        f"repl-{strategy_id}-{meal_i}",
                        strategy_id,
                        f"meal-{meal_i}",
                        "2026-07-01T00:00:00+00:00",
                    ),
                )
            await db.commit()

    asyncio.run(_finalize())


def test_migration_adds_last_review_generation_column():
    async def _run():
        import aiosqlite

        async with aiosqlite.connect(database.resolve_database_path()) as db:
            cursor = await db.execute("PRAGMA table_info(learned_preferences)")
            columns = {row[1] for row in await cursor.fetchall()}
            await cursor.close()
            assert "last_review_generation" in columns

    asyncio.run(_run())


def test_dismiss_review_persists_generation_and_survives_reload(client):
    _activate()
    for i in range(4):
        _save_finalized(i)

    listed = client.get("/api/learned-preferences").json()
    pref = listed["preferences"][0]
    assert pref["effectiveness"]["status"] == "ineffective"
    assert pref["effectiveness"]["generation"] == 1
    assert pref["last_review_generation"] is None

    dismissed = client.post(
        "/api/learned-preferences/v1:prefer_familiar_meals/dismiss-review"
    )
    assert dismissed.status_code == 200
    body = dismissed.json()["preferences"][0]
    assert body["status"] == "active"
    assert body["last_review_generation"] == 1

    reloaded = client.get("/api/learned-preferences").json()["preferences"][0]
    assert reloaded["last_review_generation"] == 1
    assert reloaded["status"] == "active"


def test_dismiss_does_not_change_status_or_require_preview_side_effects(client):
    _activate()
    for i in range(4):
        _save_finalized(i)
    before = client.get("/api/learned-preferences").json()["preferences"][0]
    after = client.post(
        "/api/learned-preferences/v1:prefer_familiar_meals/dismiss-review"
    ).json()["preferences"][0]
    assert after["status"] == before["status"] == "active"
    assert after["accepted_at"] == before["accepted_at"]
    assert after["revoked_at"] is None


def test_dismiss_rejects_non_active(client):
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
            status="revoked",
        )
    )
    response = client.post(
        "/api/learned-preferences/v1:prefer_familiar_meals/dismiss-review"
    )
    assert response.status_code == 409


def test_new_cohort_allows_review_again(client):
    _activate()
    for i in range(4):
        _save_finalized(i)
    client.post(
        "/api/learned-preferences/v1:prefer_familiar_meals/dismiss-review"
    )
    mid = client.get("/api/learned-preferences").json()["preferences"][0]
    assert mid["last_review_generation"] == 1
    assert mid["effectiveness"]["generation"] == 1

    # Add 4 more applied completed plans → generation 2.
    for i in range(4, 8):
        _save_finalized(i)
    later = client.get("/api/learned-preferences").json()["preferences"][0]
    assert later["effectiveness"]["generation"] == 2
    assert later["last_review_generation"] == 1
    # Frontend would show review again: generation > last_review_generation
    assert later["effectiveness"]["generation"] > later["last_review_generation"]
