"""Service lifecycle: candidate -> active -> revoked, creation only on accept."""

from __future__ import annotations

import asyncio

import aiosqlite
import pytest

import config
import database
from learned_preferences.exceptions import LearnedPreferenceNotFoundError
from learned_preferences.repository import preference_key
from learned_preferences.service import LearnedPreferenceService

USER_ID = 42
FAMILIAR_ID = preference_key("prefer_familiar_meals")


async def _seed_accepted_recommendation(
    recommendation_type: str = "profile_enable_prefer_familiar_meals",
    *,
    patch_json: str = '{"planning_preferences": {"prefer_familiar_meals": true}}',
) -> None:
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
            ) VALUES (?, ?, ?, ?, ?, 'accepted', ?, 1, ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                f"rec-{recommendation_type}",
                USER_ID,
                f"v1:{recommendation_type}",
                recommendation_type,
                "planning.prefer_familiar_meals",
                "strong",
                "s1",
                patch_json,
                "2026-07-10T00:00:00+00:00",
                "2026-07-10T00:00:00+00:00",
                "2026-07-11T00:00:00+00:00",
            ),
        )
        await db.commit()


@pytest.fixture
def service(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "lp-lifecycle.db"))
    asyncio.run(database.init_db())
    return LearnedPreferenceService()


def _list(service):
    return asyncio.run(service.list_preferences(USER_ID)).preferences


def test_candidate_appears_only_after_accepted_recommendation(service):
    assert _list(service) == []
    asyncio.run(_seed_accepted_recommendation())
    preferences = _list(service)
    assert len(preferences) == 1
    candidate = preferences[0]
    assert candidate.id == FAMILIAR_ID
    assert candidate.status == "candidate"
    assert candidate.type == "prefer_familiar_meals"


def test_accept_creates_active_row_with_used_since(service):
    asyncio.run(_seed_accepted_recommendation())
    response = asyncio.run(service.accept(USER_ID, FAMILIAR_ID))
    accepted = response.preferences[0]
    assert accepted.status == "active"
    assert accepted.accepted_at is not None
    # Now persisted as active; the derived candidate no longer duplicates it.
    listed = _list(service)
    assert [item.status for item in listed] == ["active"]


def test_accept_is_idempotent(service):
    asyncio.run(_seed_accepted_recommendation())
    asyncio.run(service.accept(USER_ID, FAMILIAR_ID))
    again = asyncio.run(service.accept(USER_ID, FAMILIAR_ID))
    assert again.preferences[0].status == "active"


def test_revoke_of_candidate_persists_and_hides_it(service):
    asyncio.run(_seed_accepted_recommendation())
    response = asyncio.run(service.revoke(USER_ID, FAMILIAR_ID))
    assert response.preferences[0].status == "revoked"
    listed = _list(service)
    assert [item.status for item in listed] == ["revoked"]


def test_active_can_be_revoked(service):
    asyncio.run(_seed_accepted_recommendation())
    asyncio.run(service.accept(USER_ID, FAMILIAR_ID))
    revoked = asyncio.run(service.revoke(USER_ID, FAMILIAR_ID))
    assert revoked.preferences[0].status == "revoked"
    assert revoked.preferences[0].revoked_at is not None


def test_accept_unknown_preference_raises_not_found(service):
    with pytest.raises(LearnedPreferenceNotFoundError):
        asyncio.run(service.accept(USER_ID, "v1:stable_cook_days"))


def test_no_candidate_without_accepted_recommendation(service):
    # A candidate-status recommendation must not seed a learned preference.
    async def _seed_candidate():
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
                ) VALUES (?, ?, ?, ?, ?, 'candidate', 'strong', 1, ?, ?, ?, ?, NULL, NULL, NULL)
                """,
                (
                    "rec-candidate",
                    USER_ID,
                    "v1:profile_enable_prefer_familiar_meals",
                    "profile_enable_prefer_familiar_meals",
                    "planning.prefer_familiar_meals",
                    "s1",
                    '{"planning_preferences": {"prefer_familiar_meals": true}}',
                    "2026-07-10T00:00:00+00:00",
                    "2026-07-10T00:00:00+00:00",
                ),
            )
            await db.commit()

    asyncio.run(_seed_candidate())
    assert _list(service) == []
