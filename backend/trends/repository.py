"""Read-only data access for the Trend Engine.

Loads finalized weekly strategies with their strategy-scoped evidence and
turns them into aggregate week observations. This module never writes.
"""

from __future__ import annotations

import json
import logging

import aiosqlite

import database
from decision.outcome import DecisionOutcomeCollection
from memory.constants import MemoryEventType
from strategy.records import StrategyStatus
from trends.metrics import AcceptedRecommendationObservation, WeekObservation

logger = logging.getLogger(__name__)

# History window: at most half a year of finalized weekly plans.
MAX_TREND_WEEKS = 26


def _safe_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    return default


def _preference_fingerprint(strategy_data: dict[str, object]) -> str:
    """Canonical, aggregate-only view of tracked preferences for one week."""

    def _sorted_days(key: str) -> list[int]:
        raw = strategy_data.get(key)
        if not isinstance(raw, list):
            return []
        return sorted(day for day in raw if isinstance(day, int))

    parts = (
        bool(strategy_data.get("prefer_familiar_meals")),
        bool(strategy_data.get("prefer_faster_meals")),
        tuple(_sorted_days("cook_days")),
        tuple(_sorted_days("shopping_days")),
        _safe_int(strategy_data.get("cooking_time_limit"), 0),
    )
    return repr(parts)


def _distinct_meal_count(rows: list[aiosqlite.Row]) -> int:
    distinct: set[str] = set()
    for row in rows:
        distinct.add(row["meal_id"] or row["event_key"])
    return len(distinct)


def _outcome_counts(raw: str | None) -> tuple[int, int, int, bool]:
    collection = DecisionOutcomeCollection.from_json(raw)
    if collection is None:
        return 0, 0, 0, False
    successful = sum(1 for item in collection.outcomes if item.status == "successful")
    neutral = sum(1 for item in collection.outcomes if item.status == "neutral")
    unsuccessful = sum(
        1 for item in collection.outcomes if item.status == "unsuccessful"
    )
    return successful, neutral, unsuccessful, True


class TrendRepository:
    async def load_week_observations(
        self, user_id: int, *, limit: int = MAX_TREND_WEEKS
    ) -> list[WeekObservation]:
        db_path = database.resolve_database_path()
        observations: list[WeekObservation] = []
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, plan_start_date, plan_days, strategy_json,
                       decision_outcomes_json
                FROM weekly_strategies
                WHERE user_id = ? AND status IN (?, ?)
                ORDER BY plan_start_date DESC, created_at DESC
                LIMIT ?
                """,
                (
                    user_id,
                    StrategyStatus.COMPLETED.value,
                    StrategyStatus.SUPERSEDED.value,
                    int(limit),
                ),
            )
            strategy_rows = await cursor.fetchall()
            await cursor.close()

            for row in strategy_rows:
                events_cursor = await db.execute(
                    """
                    SELECT event_type, meal_id, event_key
                    FROM memory_events
                    WHERE user_id = ? AND strategy_id = ?
                    """,
                    (user_id, row["id"]),
                )
                event_rows = await events_cursor.fetchall()
                await events_cursor.close()
                observations.append(
                    _build_observation(row, list(event_rows))
                )
        # Chronological order for windowed comparisons.
        observations.sort(key=lambda item: item.plan_start_date)
        return observations

    async def load_accepted_recommendations(
        self, user_id: int
    ) -> list[AcceptedRecommendationObservation]:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_learning_recommendations_table(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT accepted_at FROM learning_recommendations
                WHERE user_id = ? AND accepted_at IS NOT NULL
                ORDER BY accepted_at ASC
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [
            AcceptedRecommendationObservation(accepted_on=row["accepted_at"][:10])
            for row in rows
            if isinstance(row["accepted_at"], str) and len(row["accepted_at"]) >= 10
        ]


def _build_observation(
    row: aiosqlite.Row, event_rows: list[aiosqlite.Row]
) -> WeekObservation:
    try:
        strategy_data = json.loads(row["strategy_json"])
    except (json.JSONDecodeError, TypeError):
        strategy_data = {}
    if not isinstance(strategy_data, dict):
        strategy_data = {}

    days = _safe_int(strategy_data.get("days"), _safe_int(row["plan_days"], 1))
    meals_per_day = _safe_int(strategy_data.get("meals_per_day"), 3)

    by_type: dict[str, list[aiosqlite.Row]] = {}
    for event in event_rows:
        by_type.setdefault(event["event_type"], []).append(event)

    successful, neutral, unsuccessful, has_outcomes = _outcome_counts(
        row["decision_outcomes_json"]
    )
    return WeekObservation(
        plan_start_date=row["plan_start_date"],
        planned_meal_count=days * meals_per_day,
        replacement_count=_distinct_meal_count(
            by_type.get(MemoryEventType.MEAL_REPLACED.value, [])
        ),
        cooked_meal_count=_distinct_meal_count(
            by_type.get(MemoryEventType.MEAL_COOKED.value, [])
        ),
        suited_meal_count=_distinct_meal_count(
            by_type.get(MemoryEventType.MEAL_SUITED.value, [])
        ),
        shopping_completed=bool(
            by_type.get(MemoryEventType.SHOPPING_COMPLETED.value)
        ),
        plan_completed=bool(by_type.get(MemoryEventType.PLAN_COMPLETED.value)),
        outcome_successful=successful,
        outcome_neutral=neutral,
        outcome_unsuccessful=unsuccessful,
        has_outcomes=has_outcomes,
        preference_fingerprint=_preference_fingerprint(strategy_data),
    )
