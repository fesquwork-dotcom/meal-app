"""Learning recommendation persistence, idempotency, and history."""

import asyncio

import aiosqlite
import pytest

import config
import database
from learning.engine import LearningEvidence, build_learning_recommendations
from learning.repository import LearningRepository
from test_learning_engine import _outcomes, _profile


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "learning.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    asyncio.run(database.init_db())
    return path


def _draft():
    return build_learning_recommendations(
        _outcomes(),
        LearningEvidence(
            replacement_count=9,
            planned_meal_count=21,
            faster_replacement_count=0,
            suited_meal_count=0,
            cooked_meal_count=0,
            decision_prefer_familiar=False,
            decision_prefer_faster=False,
        ),
        _profile(),
    ).recommendations[0]


def test_migration_is_idempotent(db_path):
    async def columns():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "PRAGMA table_info(learning_recommendations)"
            )
            rows = await cursor.fetchall()
            await cursor.close()
            return {row[1] for row in rows}

    assert {
        "status",
        "created_at",
        "accepted_at",
        "dismissed_at",
        "expired_at",
    }.issubset(asyncio.run(columns()))
    asyncio.run(database.init_db())


def test_duplicate_prevention_includes_dismissed_history(db_path):
    repository = LearningRepository()
    first, created = asyncio.run(
        repository.create_if_absent(
            user_id=1, source_strategy_id="strategy-1", draft=_draft()
        )
    )
    assert created
    asyncio.run(
        repository.transition(
            user_id=1,
            recommendation_id=first.recommendation_id,
            target_status="dismissed",
        )
    )
    repeated, created_again = asyncio.run(
        repository.create_if_absent(
            user_id=1, source_strategy_id="strategy-2", draft=_draft()
        )
    )
    assert not created_again
    assert repeated.status == "dismissed"
    assert asyncio.run(repository.list_visible(1)) == []


def test_accept_is_idempotent_and_expiration_is_durable(db_path):
    repository = LearningRepository()
    recommendation, _ = asyncio.run(
        repository.create_if_absent(
            user_id=2, source_strategy_id="strategy-1", draft=_draft()
        )
    )
    accepted = asyncio.run(
        repository.transition(
            user_id=2,
            recommendation_id=recommendation.recommendation_id,
            target_status="accepted",
        )
    )
    accepted_again = asyncio.run(
        repository.transition(
            user_id=2,
            recommendation_id=recommendation.recommendation_id,
            target_status="accepted",
        )
    )
    assert accepted.status == accepted_again.status == "accepted"
    assert asyncio.run(repository.expire_unmatched(user_id=2, active_keys=set())) == 1
    assert asyncio.run(repository.list_visible(2)) == []


def test_malformed_patch_is_skipped_without_breaking_list(db_path):
    repository = LearningRepository()
    recommendation, _ = asyncio.run(
        repository.create_if_absent(
            user_id=3, source_strategy_id="strategy-1", draft=_draft()
        )
    )

    async def corrupt():
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                UPDATE learning_recommendations
                SET profile_patch_json = '{broken'
                WHERE id = ?
                """,
                (recommendation.recommendation_id,),
            )
            await db.commit()

    asyncio.run(corrupt())
    assert asyncio.run(repository.list_visible(3)) == []
