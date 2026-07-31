"""Read-only Strategy observations for Learned Preference effectiveness."""

from __future__ import annotations

import json
import logging
from datetime import date

import aiosqlite

import database
from decision.outcome import DecisionOutcomeCollection
from learned_preferences.effectiveness_models import (
    MAX_EFFECTIVENESS_PLANS,
    LearnedPreferencePlanObservation,
)
from memory.constants import MemoryEventType
from strategy.applied_learned_preferences import AppliedLearnedPreferencesSnapshot
from strategy.records import StrategyStatus

logger = logging.getLogger(__name__)

_DECISION_KEYS = {
    "prefer_familiar_meals": "planning.prefer_familiar_meals",
    "prefer_fast_meals": "cooking.prefer_faster",
}


def _safe_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int) and value > 0:
        return value
    return default


def _distinct_meal_count(rows: list[aiosqlite.Row]) -> int:
    distinct: set[str] = set()
    for row in rows:
        distinct.add(row["meal_id"] or row["event_key"])
    return len(distinct)


def _preference_applied(
    snapshot: AppliedLearnedPreferencesSnapshot | None,
    preference_type: str,
) -> bool:
    if snapshot is None:
        return False
    return any(
        item.preference_type == preference_type and item.applied
        for item in snapshot.decisions
    )


def _outcome_for_type(
    raw_outcomes: str | None, preference_type: str
) -> str | None:
    key = _DECISION_KEYS.get(preference_type)
    if key is None:
        return None
    collection = DecisionOutcomeCollection.from_json(raw_outcomes)
    if collection is None:
        return None
    for item in collection.outcomes:
        if item.decision_key == key:
            return item.status
    return None


class LearnedPreferenceObservationRepository:
    """Loads finalized plans where a Learned Preference was actually applied."""

    async def load_applied_plan_observations(
        self,
        user_id: int,
        preference_type: str,
        *,
        limit: int = MAX_EFFECTIVENESS_PLANS,
    ) -> list[LearnedPreferencePlanObservation]:
        if preference_type not in _DECISION_KEYS:
            return []

        db_path = database.resolve_database_path()
        observations: list[LearnedPreferencePlanObservation] = []
        # Over-fetch finalized plans then filter by applied snapshot so legacy
        # NULL rows do not consume the evidence window.
        fetch_limit = max(limit * 4, 24)

        async with aiosqlite.connect(db_path) as db:
            await database._ensure_applied_learned_preferences_column(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, plan_start_date, plan_days, strategy_json,
                       decision_outcomes_json, applied_learned_preferences_json
                FROM weekly_strategies
                WHERE user_id = ? AND status IN (?, ?)
                ORDER BY plan_start_date DESC, created_at DESC
                LIMIT ?
                """,
                (
                    user_id,
                    StrategyStatus.COMPLETED.value,
                    StrategyStatus.SUPERSEDED.value,
                    fetch_limit,
                ),
            )
            rows = await cursor.fetchall()
            await cursor.close()

            for row in rows:
                snapshot = AppliedLearnedPreferencesSnapshot.from_json(
                    row["applied_learned_preferences_json"]
                )
                if not _preference_applied(snapshot, preference_type):
                    continue

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

                observation = _build_observation(
                    row, list(event_rows), preference_type
                )
                if observation is not None:
                    observations.append(observation)
                if len(observations) >= limit:
                    break

        observations.sort(key=lambda item: item.plan_date)
        return observations


def _build_observation(
    row: aiosqlite.Row,
    event_rows: list[aiosqlite.Row],
    preference_type: str,
) -> LearnedPreferencePlanObservation | None:
    try:
        plan_date = date.fromisoformat(str(row["plan_start_date"])[:10])
    except (TypeError, ValueError):
        logger.warning("learned_preference_observation_skipped reason=bad_date")
        return None

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

    return LearnedPreferencePlanObservation(
        plan_date=plan_date,
        preference_applied=True,
        replacement_count=_distinct_meal_count(
            by_type.get(MemoryEventType.MEAL_REPLACED.value, [])
        ),
        planned_meal_count=days * meals_per_day,
        meal_suited_count=_distinct_meal_count(
            by_type.get(MemoryEventType.MEAL_SUITED.value, [])
        ),
        meal_cooked_count=_distinct_meal_count(
            by_type.get(MemoryEventType.MEAL_COOKED.value, [])
        ),
        plan_completed=bool(by_type.get(MemoryEventType.PLAN_COMPLETED.value)),
        decision_outcome=_outcome_for_type(
            row["decision_outcomes_json"], preference_type
        ),
    )
