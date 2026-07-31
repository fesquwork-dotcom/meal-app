"""SQLite persistence for memory events and preference signals."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

import aiosqlite

import database
from memory.aggregation import SignalDraft
from memory.constants import (
    ACTIVE_SIGNAL_STATUSES,
    ConfirmationSource,
    MAX_EVENTS_PER_AGGREGATION,
    MAX_SIGNALS_RETURNED,
    SignalStatus,
)
from memory.exceptions import MemoryPersistenceError, MemorySignalNotFoundError
from memory.records import MemoryEventRecord, PreferenceSignalRecord

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _event_from_row(row: aiosqlite.Row) -> MemoryEventRecord:
    return MemoryEventRecord(
        id=row["id"],
        user_id=row["user_id"],
        event_type=row["event_type"],
        event_key=row["event_key"],
        strategy_id=row["strategy_id"],
        meal_id=row["meal_id"],
        recipe_id=row["recipe_id"],
        reason_code=row["reason_code"],
        target_type=row["target_type"],
        target_value=row["target_value"],
        target_label=row["target_label"],
        metadata_json=row["metadata_json"],
        created_at=row["created_at"],
    )


def _signal_from_row(row: aiosqlite.Row) -> PreferenceSignalRecord:
    keys = set(row.keys())
    confirmation_source = (
        row["confirmation_source"] if "confirmation_source" in keys else None
    )
    promoted_at = row["promoted_at"] if "promoted_at" in keys else None
    promoted_constraint_id = (
        row["promoted_constraint_id"] if "promoted_constraint_id" in keys else None
    )
    return PreferenceSignalRecord(
        id=row["id"],
        user_id=row["user_id"],
        signal_type=row["signal_type"],
        target_value=row["target_value"],
        target_label=row["target_label"],
        status=row["status"],
        confidence=row["confidence"],
        evidence_count=row["evidence_count"],
        first_observed_at=row["first_observed_at"],
        last_observed_at=row["last_observed_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        dismissed_at=row["dismissed_at"],
        confirmation_source=confirmation_source,
        promoted_at=promoted_at,
        promoted_constraint_id=promoted_constraint_id,
    )


class MemoryRepository:
    """Persists structured feedback events and aggregated preference signals."""

    async def insert_event(self, event: MemoryEventRecord) -> bool:
        """Inserts an event idempotently by event_key. Returns True if newly inserted."""
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    """
                    INSERT OR IGNORE INTO memory_events (
                        id, user_id, event_type, event_key, strategy_id, meal_id,
                        recipe_id, reason_code, target_type, target_value, target_label,
                        metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.id,
                        event.user_id,
                        event.event_type,
                        event.event_key,
                        event.strategy_id,
                        event.meal_id,
                        event.recipe_id,
                        event.reason_code,
                        event.target_type,
                        event.target_value,
                        event.target_label,
                        event.metadata_json,
                        event.created_at,
                    ),
                )
                inserted = cursor.rowcount > 0
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise MemoryPersistenceError("Failed to save memory event") from exc
        return inserted

    async def delete_event_by_key(self, *, user_id: int, event_key: str) -> bool:
        """Deletes one user-owned event for an explicit undo action."""
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    "DELETE FROM memory_events WHERE user_id = ? AND event_key = ?",
                    (user_id, event_key),
                )
                removed = cursor.rowcount > 0
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise MemoryPersistenceError("Failed to remove memory event") from exc
        return removed

    async def list_events_for_signal(
        self,
        *,
        user_id: int,
        reason_code: str,
        target_value: str | None,
        limit: int = MAX_EVENTS_PER_AGGREGATION,
    ) -> list[MemoryEventRecord]:
        db_path = database.resolve_database_path()
        query = (
            "SELECT * FROM memory_events WHERE user_id = ? AND reason_code = ?"
        )
        params: list[object] = [user_id, reason_code]
        if target_value is not None:
            query += " AND target_value = ?"
            params.append(target_value)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(int(limit))

        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(query, tuple(params))
            rows = await cursor.fetchall()
            await cursor.close()
        return [_event_from_row(row) for row in rows]

    async def list_events_for_strategy(
        self,
        *,
        user_id: int,
        strategy_id: str,
        limit: int = MAX_EVENTS_PER_AGGREGATION,
    ) -> list[MemoryEventRecord]:
        """Load strategy-scoped evidence for retrospective evaluation."""
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM memory_events
                WHERE user_id = ? AND strategy_id = ?
                ORDER BY created_at ASC, event_key ASC
                LIMIT ?
                """,
                (user_id, strategy_id, int(limit)),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_event_from_row(row) for row in rows]

    async def get_signal(
        self, *, user_id: int, signal_type: str, target_value: str
    ) -> PreferenceSignalRecord | None:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM preference_signals
                WHERE user_id = ? AND signal_type = ? AND target_value = ?
                """,
                (user_id, signal_type, target_value),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _signal_from_row(row) if row is not None else None

    async def get_signal_by_id(self, signal_id: str, user_id: int) -> PreferenceSignalRecord:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM preference_signals WHERE id = ? AND user_id = ?",
                (signal_id, user_id),
            )
            row = await cursor.fetchone()
            await cursor.close()
        if row is None:
            raise MemorySignalNotFoundError(f"Signal {signal_id} not found")
        return _signal_from_row(row)

    async def list_active_signals(
        self, user_id: int, limit: int = MAX_SIGNALS_RETURNED
    ) -> list[PreferenceSignalRecord]:
        db_path = database.resolve_database_path()
        placeholders = ", ".join("?" for _ in ACTIVE_SIGNAL_STATUSES)
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"""
                SELECT * FROM preference_signals
                WHERE user_id = ? AND status IN ({placeholders})
                ORDER BY confidence DESC, updated_at DESC
                LIMIT ?
                """,
                (user_id, *sorted(ACTIVE_SIGNAL_STATUSES), int(limit)),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_signal_from_row(row) for row in rows]

    async def list_confirmed_signals(
        self, user_id: int, limit: int = MAX_SIGNALS_RETURNED
    ) -> list[PreferenceSignalRecord]:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM preference_signals
                WHERE user_id = ? AND status = ? AND (promoted_at IS NULL OR promoted_at = '')
                ORDER BY signal_type ASC, target_value ASC, updated_at DESC
                LIMIT ?
                """,
                (user_id, SignalStatus.CONFIRMED.value, int(limit)),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_signal_from_row(row) for row in rows]

    async def upsert_signal(self, user_id: int, draft: SignalDraft, now_iso: str) -> None:
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                await db.execute(
                    """
                    INSERT INTO preference_signals (
                        id, user_id, signal_type, target_value, target_label,
                        status, confidence, evidence_count,
                        first_observed_at, last_observed_at,
                        created_at, updated_at, dismissed_at, confirmation_source
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?)
                    ON CONFLICT(user_id, signal_type, target_value) DO UPDATE SET
                        target_label = excluded.target_label,
                        status = excluded.status,
                        confidence = excluded.confidence,
                        evidence_count = excluded.evidence_count,
                        first_observed_at = excluded.first_observed_at,
                        last_observed_at = excluded.last_observed_at,
                        updated_at = excluded.updated_at,
                        dismissed_at = NULL,
                        confirmation_source = COALESCE(
                            preference_signals.confirmation_source,
                            excluded.confirmation_source
                        )
                    """,
                    (
                        str(uuid.uuid4()),
                        user_id,
                        draft.signal_type,
                        draft.target_value,
                        draft.target_label,
                        draft.status,
                        draft.confidence,
                        draft.evidence_count,
                        draft.first_observed_at,
                        draft.last_observed_at,
                        now_iso,
                        now_iso,
                        draft.confirmation_source,
                    ),
                )
                await db.commit()
        except aiosqlite.Error as exc:
            raise MemoryPersistenceError("Failed to upsert preference signal") from exc

    async def set_status(
        self,
        *,
        signal_id: str,
        user_id: int,
        status: str,
        confidence: float | None,
        now_iso: str,
        confirmation_source: str | None = None,
    ) -> PreferenceSignalRecord:
        db_path = database.resolve_database_path()
        dismissed_at = now_iso if status == SignalStatus.DISMISSED.value else None
        try:
            async with aiosqlite.connect(db_path) as db:
                if confidence is None and confirmation_source is None:
                    cursor = await db.execute(
                        """
                        UPDATE preference_signals
                        SET status = ?, updated_at = ?, dismissed_at = ?
                        WHERE id = ? AND user_id = ?
                        """,
                        (status, now_iso, dismissed_at, signal_id, user_id),
                    )
                elif confidence is None:
                    cursor = await db.execute(
                        """
                        UPDATE preference_signals
                        SET status = ?, updated_at = ?, dismissed_at = ?,
                            confirmation_source = ?
                        WHERE id = ? AND user_id = ?
                        """,
                        (
                            status,
                            now_iso,
                            dismissed_at,
                            confirmation_source,
                            signal_id,
                            user_id,
                        ),
                    )
                elif confirmation_source is None:
                    cursor = await db.execute(
                        """
                        UPDATE preference_signals
                        SET status = ?, confidence = ?, updated_at = ?, dismissed_at = ?
                        WHERE id = ? AND user_id = ?
                        """,
                        (status, confidence, now_iso, dismissed_at, signal_id, user_id),
                    )
                else:
                    cursor = await db.execute(
                        """
                        UPDATE preference_signals
                        SET status = ?, confidence = ?, updated_at = ?, dismissed_at = ?,
                            confirmation_source = ?
                        WHERE id = ? AND user_id = ?
                        """,
                        (
                            status,
                            confidence,
                            now_iso,
                            dismissed_at,
                            confirmation_source,
                            signal_id,
                            user_id,
                        ),
                    )
                changed = cursor.rowcount
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise MemoryPersistenceError("Failed to update signal status") from exc

        if changed == 0:
            raise MemorySignalNotFoundError(f"Signal {signal_id} not found")
        return await self.get_signal_by_id(signal_id, user_id)
