"""Integration tests for BehaviorLearningEngine."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest

import config
import database
from behavior.constants import BehaviorInsightStatus, BehaviorInsightType
from behavior.engine import BehaviorLearningEngine
from behavior.exceptions import BehaviorEvaluationError
from behavior.repository import BehaviorRepository
from memory.records import MemoryEventRecord
from memory.repository import MemoryRepository

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "behavior-engine-test.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    asyncio.run(database.init_db())
    return path


@pytest.fixture
def memory_repository(db_path):
    return MemoryRepository()


@pytest.fixture
def behavior_repository(db_path):
    return BehaviorRepository()


@pytest.fixture
def engine(memory_repository, behavior_repository):
    return BehaviorLearningEngine(
        behavior_repository=behavior_repository,
        memory_repository=memory_repository,
    )


def _event(key: str, *, recipe_id: str = "recipe-a", reason_code: str = "generic") -> MemoryEventRecord:
    return MemoryEventRecord(
        id=f"evt-{key}",
        user_id=42,
        event_type="meal_replaced",
        event_key=key,
        strategy_id="s1",
        meal_id="day1_lunch",
        recipe_id=recipe_id,
        reason_code=reason_code,
        target_type=None,
        target_value=None,
        target_label=None,
        metadata_json=None,
        created_at=NOW.isoformat(),
    )


async def _insert_event(repo: MemoryRepository, event: MemoryEventRecord) -> None:
    await repo.insert_event(event)


async def _insert_strategy(user_id: int, strategy_id: str, created_at: str) -> None:
    async with aiosqlite.connect(config.DATABASE_PATH) as db:
        await db.execute(
            """
            INSERT INTO weekly_strategies (
                id, user_id, strategy_version, status, plan_start_date, plan_days,
                strategy_json, created_at, updated_at
            ) VALUES (?, ?, 1, 'completed', '2026-07-01', 7, '{}', ?, ?)
            """,
            (strategy_id, user_id, created_at, created_at),
        )
        await db.commit()


async def _save_profile(user_id: int, dietary_constraints: list | None = None) -> None:
    await database.save_profile(
        user_id,
        {
            "first_name": "Test",
            "budget": 1000,
            "days": 7,
            "persons": 1,
            "proteins": ["any"],
            "goal": "home",
            "cooktime": "medium",
            "allergies": "",
            "store": "",
            "dietary_constraints": dietary_constraints or [],
        },
    )


def test_engine_creates_candidates_from_events(engine, memory_repository):
    async def _run():
        await _insert_event(memory_repository, _event("e1"))
        await _insert_event(memory_repository, _event("e2"))
        return await engine.evaluate_user(42, now=NOW)

    result = asyncio.run(_run())
    assert result.created_count == 1
    assert result.candidate_count == 1


def test_engine_idempotent_on_repeat(engine, memory_repository):
    async def _run():
        await _insert_event(memory_repository, _event("e1"))
        await _insert_event(memory_repository, _event("e2"))
        first = await engine.evaluate_user(42, now=NOW)
        second = await engine.evaluate_user(42, now=NOW)
        return first, second

    first, second = asyncio.run(_run())
    assert first.created_count == 1
    assert second.created_count == 0
    assert second.updated_count == 0
    assert second.unchanged_count == 1


def test_engine_observed_to_candidate_transition(engine, memory_repository):
    async def _run():
        await _insert_event(memory_repository, _event("e1"))
        first = await engine.evaluate_user(42, now=NOW)
        await _insert_event(memory_repository, _event("e2"))
        second = await engine.evaluate_user(42, now=NOW)
        return first, second

    first, second = asyncio.run(_run())
    assert first.observed_count == 1
    assert second.candidate_count == 1
    assert second.updated_count == 1


def test_engine_confirmed_never_downgraded(engine, behavior_repository, memory_repository):
    async def _run():
        await _insert_event(memory_repository, _event("e1"))
        await _insert_event(memory_repository, _event("e2"))
        await engine.evaluate_user(42, now=NOW)
        rows = await behavior_repository.list_by_status(
            42, [BehaviorInsightStatus.CANDIDATE.value]
        )
        confirmed = await behavior_repository.confirm(42, rows[0].id, now=NOW)
        await _insert_event(memory_repository, _event("e3"))
        result = await engine.evaluate_user(42, now=NOW)
        reloaded = await behavior_repository.get_by_id(42, confirmed.id)
        return result, reloaded

    result, reloaded = asyncio.run(_run())
    assert reloaded.status == BehaviorInsightStatus.CONFIRMED.value
    assert result.updated_count >= 0


def test_engine_dismissed_never_reopened(engine, behavior_repository, memory_repository):
    async def _run():
        await _insert_event(memory_repository, _event("e1"))
        await _insert_event(memory_repository, _event("e2"))
        await engine.evaluate_user(42, now=NOW)
        rows = await behavior_repository.list_by_status(
            42, [BehaviorInsightStatus.CANDIDATE.value]
        )
        dismissed = await behavior_repository.dismiss(42, rows[0].id, now=NOW)
        await _insert_event(memory_repository, _event("e3"))
        await engine.evaluate_user(42, now=NOW)
        return await behavior_repository.get_by_id(42, dismissed.id)

    reloaded = asyncio.run(_run())
    assert reloaded.status == BehaviorInsightStatus.DISMISSED.value


def test_engine_expires_due_insights(engine, behavior_repository, memory_repository):
    async def _run():
        await _insert_event(memory_repository, _event("e1"))
        await _insert_event(memory_repository, _event("e2"))
        await engine.evaluate_user(42, now=NOW)
        rows = await behavior_repository.list_by_status(
            42, [BehaviorInsightStatus.CANDIDATE.value]
        )
        past = NOW + timedelta(days=200)
        result = await engine.evaluate_user(42, now=past)
        reloaded = await behavior_repository.get_by_id(42, rows[0].id)
        return result, reloaded

    result, reloaded = asyncio.run(_run())
    assert result.expired_count >= 1
    assert reloaded.status == BehaviorInsightStatus.EXPIRED.value


def test_engine_policy_filters_profile_exclusion(engine, behavior_repository, memory_repository):
    async def _run():
        await _save_profile(
            42,
            dietary_constraints=[
                {
                    "id": "c1",
                    "kind": "preference",
                    "value": "гречка",
                    "canonical_value": "гречка",
                }
            ],
        )
        await _insert_event(
            memory_repository,
            MemoryEventRecord(
                id="evt-u1",
                user_id=42,
                event_type="meal_replaced",
                event_key="u1",
                strategy_id="s1",
                meal_id="day1_lunch",
                recipe_id="recipe-a",
                reason_code="ingredient_unavailable",
                target_type="ingredient",
                target_value="гречка",
                target_label="Гречка",
                metadata_json=None,
                created_at=NOW.isoformat(),
            ),
        )
        await _insert_event(
            memory_repository,
            MemoryEventRecord(
                id="evt-u2",
                user_id=42,
                event_type="meal_replaced",
                event_key="u2",
                strategy_id="s1",
                meal_id="day2_lunch",
                recipe_id="recipe-b",
                reason_code="ingredient_unavailable",
                target_type="ingredient",
                target_value="гречка",
                target_label="Гречка",
                metadata_json=None,
                created_at=(NOW + timedelta(hours=1)).isoformat(),
            ),
        )
        result = await engine.evaluate_user(42, now=NOW)
        rows = await behavior_repository.list_by_status(
            42,
            [
                BehaviorInsightStatus.CANDIDATE.value,
                BehaviorInsightStatus.OBSERVED.value,
            ],
        )
        friction = [
            row
            for row in rows
            if row.insight_type == BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION.value
        ]
        return result, friction

    result, friction = asyncio.run(_run())
    assert friction == []


def test_engine_high_replacement_rate_with_strategy_count(engine, behavior_repository, memory_repository):
    async def _run():
        created_at = NOW.isoformat()
        await _insert_strategy(42, "ws-1", created_at)
        await _insert_strategy(42, "ws-2", created_at)
        for index in range(5):
            await _insert_event(memory_repository, _event(f"hr-{index}"))
        result = await engine.evaluate_user(42, now=NOW)
        rows = await behavior_repository.list_by_status(
            42, [BehaviorInsightStatus.CANDIDATE.value]
        )
        global_rows = [
            row
            for row in rows
            if row.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE.value
        ]
        return result, global_rows

    result, global_rows = asyncio.run(_run())
    assert len(global_rows) == 1
    assert result.candidate_count >= 1


def test_engine_does_not_mutate_memory_events(engine, memory_repository, db_path):
    async def _run():
        event = _event("immutable")
        await _insert_event(memory_repository, event)
        await _insert_event(memory_repository, _event("e2"))
        await engine.evaluate_user(42, now=NOW)
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT recipe_id, reason_code FROM memory_events WHERE event_key = ?",
                ("immutable",),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return row

    row = asyncio.run(_run())
    assert row == ("recipe-a", "generic")


def test_behavior_package_import_smoke():
    import behavior

    assert behavior.BehaviorLearningEngine is not None
