"""SQLite persistence for weekly strategies."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import date, datetime, timezone

import aiosqlite
from pydantic import ValidationError

import database
from decision.context import DecisionContext
from decision.outcome import DecisionOutcomeCollection
from decision.repository import DecisionRepository
from decision.trace_models import DecisionTrace
from strategy.applied_behavior import AppliedBehaviorSnapshot
from strategy.applied_cooking import AppliedCookingPreference
from strategy.applied_learned_preferences import AppliedLearnedPreferencesSnapshot
from strategy.applied_planning import AppliedPlanningPreferences
from strategy.exceptions import (
    StrategyNotFoundError,
    StrategyPersistenceError,
    UnsupportedStrategyVersionError,
)
from menu_plan import sql as menu_plan_sql
from strategy.memory_context import AppliedMemorySnapshot
from strategy.models import WeeklyStrategy
from strategy.records import StrategyRecord, StrategyStatus, VALID_STRATEGY_STATUSES

logger = logging.getLogger(__name__)

SUPPORTED_STRATEGY_VERSIONS: frozenset[int] = frozenset({1, 2, 3, 4, 5})


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_record(row: aiosqlite.Row) -> StrategyRecord:
    keys = set(row.keys())
    reason_codes_json = row["reason_codes_json"] if "reason_codes_json" in keys else None
    applied_memory_json = row["applied_memory_json"] if "applied_memory_json" in keys else None
    applied_cooking_preferences_json = (
        row["applied_cooking_preferences_json"]
        if "applied_cooking_preferences_json" in keys
        else None
    )
    applied_behavior_json = row["applied_behavior_json"] if "applied_behavior_json" in keys else None
    applied_planning_preferences_json = (
        row["applied_planning_preferences_json"]
        if "applied_planning_preferences_json" in keys
        else None
    )
    applied_learned_preferences_json = (
        row["applied_learned_preferences_json"]
        if "applied_learned_preferences_json" in keys
        else None
    )
    decision_context_json = (
        row["decision_context_json"] if "decision_context_json" in keys else None
    )
    decision_trace_json = (
        row["decision_trace_json"] if "decision_trace_json" in keys else None
    )
    decision_outcomes_json = (
        row["decision_outcomes_json"] if "decision_outcomes_json" in keys else None
    )
    return StrategyRecord(
        id=row["id"],
        user_id=row["user_id"],
        strategy_version=row["strategy_version"],
        status=row["status"],
        plan_start_date=row["plan_start_date"],
        plan_days=row["plan_days"],
        strategy_json=row["strategy_json"],
        reason_codes_json=reason_codes_json,
        applied_memory_json=applied_memory_json,
        applied_cooking_preferences_json=applied_cooking_preferences_json,
        applied_behavior_json=applied_behavior_json,
        applied_planning_preferences_json=applied_planning_preferences_json,
        applied_learned_preferences_json=applied_learned_preferences_json,
        decision_context_json=decision_context_json,
        decision_trace_json=decision_trace_json,
        decision_outcomes_json=decision_outcomes_json,
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
        superseded_at=row["superseded_at"],
    )


def _parse_weekly_strategy(record: StrategyRecord) -> WeeklyStrategy:
    if record.strategy_version not in SUPPORTED_STRATEGY_VERSIONS:
        raise UnsupportedStrategyVersionError(record.strategy_version)

    try:
        strategy = WeeklyStrategy.from_json(record.strategy_json)
    except (ValidationError, ValueError, TypeError) as exc:
        raise StrategyPersistenceError("Stored strategy JSON is malformed") from exc

    if strategy.strategy_version != record.strategy_version:
        raise StrategyPersistenceError("strategy_version column does not match strategy_json")

    return strategy


def _parse_reason_codes(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("strategy_reason_codes_malformed")
        return None
    if not isinstance(parsed, list):
        return None
    return [item for item in parsed if isinstance(item, str) and item.strip()]


class StrategyRepository:
    """Persists immutable weekly strategy snapshots and lifecycle status."""

    async def save_active(
        self,
        *,
        user_id: int,
        strategy: WeeklyStrategy,
        plan_start_date: date,
        reason_codes: list[str] | None = None,
        applied_memory: AppliedMemorySnapshot | None = None,
        applied_cooking_preference: AppliedCookingPreference | None = None,
        applied_behavior: AppliedBehaviorSnapshot | None = None,
        applied_planning_preferences: AppliedPlanningPreferences | None = None,
        applied_learned_preferences: AppliedLearnedPreferencesSnapshot | None = None,
        decision_context: DecisionContext | None = None,
        decision_trace: DecisionTrace | None = None,
        menu_plan_id: str | None = None,
        menu_plan_json: str | None = None,
    ) -> str:
        """Supersede previous active strategy and insert a new active snapshot atomically.

        Sprint 7.2: when a generated menu accompanies the strategy, its
        immutable snapshot is written in the SAME transaction, so a strategy
        can never be committed without its durable MenuPlan (and vice versa).
        """
        strategy_id = str(uuid.uuid4())
        now = _utc_now_iso()
        plan_start_iso = plan_start_date.isoformat()
        reason_codes_json = json.dumps(reason_codes or [], ensure_ascii=False)
        snapshot = applied_memory or AppliedMemorySnapshot.empty()
        applied_memory_json = snapshot.to_json()
        applied_cooking_json = (
            applied_cooking_preference.to_json() if applied_cooking_preference is not None else None
        )
        applied_behavior_json = (
            applied_behavior.to_json() if applied_behavior is not None else None
        )
        applied_planning_json = (
            applied_planning_preferences.to_json()
            if applied_planning_preferences is not None
            else None
        )
        applied_learned_json = (
            applied_learned_preferences.to_json()
            if applied_learned_preferences is not None
            else None
        )
        decision_context_json = DecisionRepository.dump(decision_context)
        decision_trace_json = decision_trace.to_json() if decision_trace is not None else None

        db_path = database.resolve_database_path()

        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_applied_planning_preferences_column(db)
                await database._ensure_applied_learned_preferences_column(db)
                await database._ensure_decision_context_column(db)
                await database._ensure_decision_trace_column(db)
                await database._ensure_decision_outcomes_column(db)
                await database._ensure_menu_plan_tables(db)
                await db.execute("BEGIN IMMEDIATE")
                cursor = await db.execute(
                    """
                    SELECT id FROM weekly_strategies
                    WHERE user_id = ? AND status = ?
                    """,
                    (user_id, StrategyStatus.ACTIVE.value),
                )
                previous = await cursor.fetchone()
                await cursor.close()

                if previous is not None:
                    previous_id = previous[0]
                    await db.execute(
                        """
                        UPDATE weekly_strategies
                        SET status = ?, superseded_at = ?, updated_at = ?
                        WHERE id = ?
                        """,
                        (StrategyStatus.SUPERSEDED.value, now, now, previous_id),
                    )
                    logger.info(
                        "strategy_lifecycle_transition strategy_id=%s user_id=%s "
                        "from_status=active to_status=superseded",
                        previous_id,
                        user_id,
                    )

                await db.execute(
                    """
                    INSERT INTO weekly_strategies (
                        id, user_id, strategy_version, status,
                        plan_start_date, plan_days, strategy_json,
                        reason_codes_json, applied_memory_json,
                        applied_cooking_preferences_json, applied_behavior_json,
                        applied_planning_preferences_json,
                        applied_learned_preferences_json, decision_context_json,
                        decision_trace_json,
                        created_at, updated_at, completed_at, superseded_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
                    """,
                    (
                        strategy_id,
                        user_id,
                        strategy.strategy_version,
                        StrategyStatus.ACTIVE.value,
                        plan_start_iso,
                        strategy.days,
                        strategy.to_json(),
                        reason_codes_json,
                        applied_memory_json,
                        applied_cooking_json,
                        applied_behavior_json,
                        applied_planning_json,
                        applied_learned_json,
                        decision_context_json,
                        decision_trace_json,
                        now,
                        now,
                    ),
                )
                if menu_plan_id is not None and menu_plan_json is not None:
                    await menu_plan_sql.supersede_active_menu_plans(
                        db, user_id=user_id, now=now
                    )
                    await menu_plan_sql.insert_initial_menu_plan(
                        db,
                        menu_plan_id=menu_plan_id,
                        user_id=user_id,
                        strategy_id=strategy_id,
                        plan_json=menu_plan_json,
                        now=now,
                    )
                await db.commit()
        except aiosqlite.Error as exc:
            logger.error(
                "strategy_save_failed user_id=%s strategy_version=%s plan_start_date=%s error=%s",
                user_id,
                strategy.strategy_version,
                plan_start_iso,
                exc,
            )
            raise StrategyPersistenceError("Failed to save weekly strategy") from exc

        logger.info(
            "strategy_saved strategy_id=%s user_id=%s status=active strategy_version=%s "
            "plan_start_date=%s plan_days=%s decision_version=%s",
            strategy_id,
            user_id,
            strategy.strategy_version,
            plan_start_iso,
            strategy.days,
            decision_context.decision_version if decision_context is not None else None,
        )
        if decision_trace is not None:
            logger.info(
                "decision_trace_saved strategy_id=%s trace_version=%s decision_count=%s",
                strategy_id,
                decision_trace.trace_version,
                len(decision_trace.entries),
            )
        if menu_plan_id is not None and menu_plan_json is not None:
            logger.info(
                "menu_plan_saved menu_plan_id=%s strategy_id=%s revision=1",
                menu_plan_id,
                strategy_id,
            )
        return strategy_id

    async def get_active_for_user(self, user_id: int) -> StrategyRecord | None:
        db_path = database.resolve_database_path()

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM weekly_strategies
                WHERE user_id = ? AND status = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, StrategyStatus.ACTIVE.value),
            )
            row = await cursor.fetchone()
            await cursor.close()

        if row is None:
            return None

        return _row_to_record(row)

    async def get_latest_finalized_for_user(
        self, user_id: int
    ) -> StrategyRecord | None:
        """Latest completed/superseded strategy for read-only retrospectives."""
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM weekly_strategies
                WHERE user_id = ? AND status IN (?, ?)
                ORDER BY plan_start_date DESC, created_at DESC
                LIMIT 1
                """,
                (
                    user_id,
                    StrategyStatus.COMPLETED.value,
                    StrategyStatus.SUPERSEDED.value,
                ),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _row_to_record(row) if row is not None else None

    async def get_by_id(self, strategy_id: str, user_id: int) -> StrategyRecord:
        db_path = database.resolve_database_path()

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM weekly_strategies WHERE id = ? AND user_id = ?",
                (strategy_id, user_id),
            )
            row = await cursor.fetchone()
            await cursor.close()

        if row is None:
            raise StrategyNotFoundError(f"Strategy {strategy_id} not found")

        return _row_to_record(row)

    async def mark_completed(self, strategy_id: str, user_id: int) -> None:
        now = _utc_now_iso()
        db_path = database.resolve_database_path()

        try:
            async with aiosqlite.connect(db_path) as db:
                await db.execute("BEGIN IMMEDIATE")
                cursor = await db.execute(
                    """
                    UPDATE weekly_strategies
                    SET status = ?, completed_at = ?, updated_at = ?
                    WHERE id = ? AND user_id = ? AND status = ?
                    """,
                    (
                        StrategyStatus.COMPLETED.value,
                        now,
                        now,
                        strategy_id,
                        user_id,
                        StrategyStatus.ACTIVE.value,
                    ),
                )
                if cursor.rowcount == 0:
                    await db.rollback()
                    raise StrategyNotFoundError(f"Active strategy {strategy_id} not found")
                await db.commit()
        except aiosqlite.Error as exc:
            raise StrategyPersistenceError("Failed to mark strategy completed") from exc

        logger.info(
            "strategy_lifecycle_transition strategy_id=%s user_id=%s "
            "from_status=active to_status=completed",
            strategy_id,
            user_id,
        )

    async def supersede_active(self, user_id: int) -> str | None:
        """Mark current active strategy as superseded without creating a replacement."""
        now = _utc_now_iso()
        db_path = database.resolve_database_path()

        async with aiosqlite.connect(db_path) as db:
            await db.execute("BEGIN IMMEDIATE")
            cursor = await db.execute(
                """
                SELECT id FROM weekly_strategies
                WHERE user_id = ? AND status = ?
                """,
                (user_id, StrategyStatus.ACTIVE.value),
            )
            row = await cursor.fetchone()
            await cursor.close()

            if row is None:
                await db.rollback()
                return None

            strategy_id = row[0]
            await db.execute(
                """
                UPDATE weekly_strategies
                SET status = ?, superseded_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (StrategyStatus.SUPERSEDED.value, now, now, strategy_id),
            )
            await db.commit()

        logger.info(
            "strategy_lifecycle_transition strategy_id=%s user_id=%s "
            "from_status=active to_status=superseded",
            strategy_id,
            user_id,
        )
        return strategy_id

    def load_reason_codes(self, record: StrategyRecord) -> list[str] | None:
        return _parse_reason_codes(record.reason_codes_json)

    def load_applied_memory(self, record: StrategyRecord) -> AppliedMemorySnapshot | None:
        return AppliedMemorySnapshot.from_json(record.applied_memory_json)

    def load_applied_cooking_preference(
        self, record: StrategyRecord
    ) -> AppliedCookingPreference | None:
        return AppliedCookingPreference.from_json(record.applied_cooking_preferences_json)

    def load_applied_behavior(self, record: StrategyRecord) -> AppliedBehaviorSnapshot | None:
        return AppliedBehaviorSnapshot.from_json(record.applied_behavior_json)

    def load_applied_planning_preferences(
        self, record: StrategyRecord
    ) -> AppliedPlanningPreferences | None:
        return AppliedPlanningPreferences.from_json(record.applied_planning_preferences_json)

    def load_applied_learned_preferences(
        self, record: StrategyRecord
    ) -> AppliedLearnedPreferencesSnapshot | None:
        return AppliedLearnedPreferencesSnapshot.from_json(
            record.applied_learned_preferences_json
        )

    def load_decision_context(self, record: StrategyRecord) -> DecisionContext | None:
        return DecisionRepository.load(record.decision_context_json)

    def load_decision_trace(self, record: StrategyRecord) -> DecisionTrace | None:
        if not record.decision_trace_json:
            logger.info(
                "decision_trace_unavailable strategy_id=%s reason=missing strategy_version=%s",
                record.id,
                record.strategy_version,
            )
            return None
        trace = DecisionTrace.from_json(record.decision_trace_json)
        if trace is None:
            # Malformed trace never blocks the strategy itself.
            logger.warning(
                "decision_trace_unavailable strategy_id=%s reason=invalid",
                record.id,
            )
            return None
        logger.info(
            "decision_trace_loaded strategy_id=%s trace_version=%s decision_count=%s",
            record.id,
            trace.trace_version,
            len(trace.entries),
        )
        return trace

    def load_decision_outcomes(
        self, record: StrategyRecord
    ) -> DecisionOutcomeCollection | None:
        outcomes = DecisionOutcomeCollection.from_json(record.decision_outcomes_json)
        if record.decision_outcomes_json and outcomes is None:
            logger.warning(
                "decision_outcomes_unavailable strategy_id=%s reason=invalid",
                record.id,
            )
        return outcomes

    async def save_decision_outcomes_if_absent(
        self,
        *,
        strategy_id: str,
        user_id: int,
        outcomes: DecisionOutcomeCollection,
    ) -> bool:
        """Write the retrospective snapshot once; later evaluations cannot replace it."""
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_decision_outcomes_column(db)
                await db.execute("BEGIN IMMEDIATE")
                cursor = await db.execute(
                    """
                    UPDATE weekly_strategies
                    SET decision_outcomes_json = ?
                    WHERE id = ? AND user_id = ?
                      AND decision_outcomes_json IS NULL
                      AND status IN (?, ?)
                    """,
                    (
                        outcomes.to_json(),
                        strategy_id,
                        user_id,
                        StrategyStatus.COMPLETED.value,
                        StrategyStatus.SUPERSEDED.value,
                    ),
                )
                saved = cursor.rowcount > 0
                await cursor.close()
                if saved:
                    await db.commit()
                else:
                    await db.rollback()
        except aiosqlite.Error as exc:
            raise StrategyPersistenceError(
                "Failed to save decision outcomes"
            ) from exc
        if saved:
            logger.info(
                "decision_outcomes_saved strategy_id=%s outcome_count=%s",
                strategy_id,
                len(outcomes.outcomes),
            )
        return saved

    def restore_weekly_strategy(self, record: StrategyRecord) -> WeeklyStrategy:
        return _parse_weekly_strategy(record)

    @staticmethod
    def validate_status(status: str) -> None:
        if status not in VALID_STRATEGY_STATUSES:
            raise StrategyPersistenceError(f"Invalid strategy status: {status}")
