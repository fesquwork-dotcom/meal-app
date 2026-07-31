"""Read-only observation loading for the Trend Engine."""

import asyncio
import json
from dataclasses import replace
from datetime import date, datetime, timezone

import aiosqlite
import pytest

import config
import database
from decision.engine import DecisionEngine
from decision.outcome import evaluate_decision_outcomes
from memory.repository import MemoryRepository
from strategy.repository import StrategyRepository
from test_decision_outcomes import _event
from trends.repository import TrendRepository


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "trends-repo.db"))
    asyncio.run(database.init_db())


def _seed_week(
    *,
    user_id: int = 7,
    plan_start: date,
    replacements: int = 0,
    positive: bool = False,
    with_outcomes: bool = False,
) -> str:
    evaluation = DecisionEngine().evaluate({"days": 7, "goal": "home"})
    repository = StrategyRepository()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=user_id,
            strategy=evaluation.strategy,
            plan_start_date=plan_start,
            reason_codes=evaluation.reason_codes,
            decision_context=evaluation.decision,
            decision_trace=evaluation.trace,
        )
    )
    memory = MemoryRepository()
    events = []
    for index in range(replacements):
        event = replace(
            _event(index),
            id=f"{strategy_id}-replaced-{index}",
            event_key=f"{strategy_id}-request-{index}",
            user_id=user_id,
            strategy_id=strategy_id,
        )
        events.append(event)
        asyncio.run(memory.insert_event(event))
    if positive:
        cooked = replace(
            _event(90),
            id=f"{strategy_id}-cooked",
            event_key=f"{strategy_id}-cooked-key",
            event_type="meal_cooked",
            user_id=user_id,
            strategy_id=strategy_id,
        )
        asyncio.run(memory.insert_event(cooked))
    asyncio.run(repository.mark_completed(strategy_id, user_id))
    if with_outcomes:
        outcomes = evaluate_decision_outcomes(
            evaluation.trace, events, strategy=evaluation.strategy
        )
        assert asyncio.run(
            repository.save_decision_outcomes_if_absent(
                strategy_id=strategy_id, user_id=user_id, outcomes=outcomes
            )
        )
    return strategy_id


def test_observations_are_chronological_and_aggregated(db):
    _seed_week(plan_start=date(2026, 6, 8), replacements=2, positive=True)
    _seed_week(plan_start=date(2026, 6, 1), replacements=5, with_outcomes=True)

    observations = asyncio.run(TrendRepository().load_week_observations(7))
    assert len(observations) == 2
    assert observations[0].plan_start_date == "2026-06-01"
    assert observations[1].plan_start_date == "2026-06-08"
    assert observations[0].replacement_count == 5
    assert observations[0].has_outcomes is True
    assert observations[1].replacement_count == 2
    assert observations[1].cooked_meal_count == 1
    assert observations[1].has_outcomes is False
    assert observations[0].planned_meal_count > 0


def test_observations_scoped_per_user(db):
    _seed_week(user_id=7, plan_start=date(2026, 6, 1), replacements=3)
    _seed_week(user_id=8, plan_start=date(2026, 6, 1), replacements=9)
    observations = asyncio.run(TrendRepository().load_week_observations(7))
    assert len(observations) == 1
    assert observations[0].replacement_count == 3


def test_malformed_strategy_json_degrades_gracefully(db):
    strategy_id = _seed_week(plan_start=date(2026, 6, 1))

    async def corrupt():
        async with aiosqlite.connect(database.resolve_database_path()) as conn:
            await conn.execute(
                "UPDATE weekly_strategies SET strategy_json = ? WHERE id = ?",
                ("{not json", strategy_id),
            )
            await conn.commit()

    asyncio.run(corrupt())
    observations = asyncio.run(TrendRepository().load_week_observations(7))
    assert len(observations) == 1
    # Falls back to plan_days-based estimate instead of failing.
    assert observations[0].planned_meal_count > 0


def test_accepted_recommendations_expose_dates_only(db):
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    async def insert_accepted():
        async with aiosqlite.connect(database.resolve_database_path()) as conn:
            await database._ensure_learning_recommendations_table(conn)
            await conn.execute(
                """
                INSERT INTO learning_recommendations (
                    id, user_id, recommendation_key, recommendation_type,
                    decision_key, status, confidence, rule_version,
                    source_strategy_id, profile_patch_json,
                    created_at, updated_at, accepted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "trend-accept-1",
                    7,
                    "v1:profile_enable_prefer_familiar_meals",
                    "profile_enable_prefer_familiar_meals",
                    "planning.prefer_familiar_meals",
                    "accepted",
                    "moderate",
                    1,
                    "source-strategy",
                    json.dumps(
                        {"planning_preferences": {"prefer_familiar_meals": True}}
                    ),
                    now,
                    now,
                    "2026-06-15T10:00:00+00:00",
                ),
            )
            await conn.commit()

    asyncio.run(insert_accepted())
    accepted = asyncio.run(TrendRepository().load_accepted_recommendations(7))
    assert len(accepted) == 1
    assert accepted[0].accepted_on == "2026-06-15"

    other_user = asyncio.run(TrendRepository().load_accepted_recommendations(8))
    assert other_user == []
