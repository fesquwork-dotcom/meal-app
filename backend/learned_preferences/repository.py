"""SQLite persistence for Learned Preferences.

Append-only lifecycle: content columns (type, source, version, evidence_json,
preference_json, created_at) are written once and never updated. Lifecycle
transitions touch only ``status`` plus the matching timestamp column. Rows are
never deleted.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import aiosqlite

import database
from learned_preferences.exceptions import (
    LearnedPreferenceNotAvailableError,
    LearnedPreferenceNotFoundError,
    LearnedPreferencePersistenceError,
)
from learned_preferences.models import LEARNED_PREFERENCE_VERSION
from learned_preferences.records import LearnedPreferenceRecord

logger = logging.getLogger(__name__)

_TIMESTAMP_COLUMNS = {
    "accepted": "accepted_at",
    "active": "accepted_at",
    "revoked": "revoked_at",
    "archived": "archived_at",
}


def preference_key(preference_type: str) -> str:
    """Deterministic per-type id; unique per user, blocks duplicates."""
    return f"v{LEARNED_PREFERENCE_VERSION}:{preference_type}"


def _utc_now_iso(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_record(row: aiosqlite.Row) -> LearnedPreferenceRecord:
    keys = set(row.keys())
    last_review_generation = None
    if "last_review_generation" in keys:
        raw = row["last_review_generation"]
        if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 0:
            last_review_generation = raw
    return LearnedPreferenceRecord(
        id=row["id"],
        user_id=row["user_id"],
        type=row["type"],
        status=row["status"],
        source=row["source"],
        version=row["version"],
        evidence_json=row["evidence_json"],
        preference_json=row["preference_json"],
        created_at=row["created_at"],
        accepted_at=row["accepted_at"],
        revoked_at=row["revoked_at"],
        archived_at=row["archived_at"],
        last_review_generation=last_review_generation,
    )


class LearnedPreferenceRepository:
    async def list_for_user(self, user_id: int) -> list[LearnedPreferenceRecord]:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_learned_preferences_table(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM learned_preferences
                WHERE user_id = ?
                ORDER BY created_at DESC, id ASC
                LIMIT 50
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_record(row) for row in rows]

    async def get(
        self, user_id: int, preference_id: str
    ) -> LearnedPreferenceRecord | None:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_learned_preferences_table(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM learned_preferences WHERE user_id = ? AND id = ?",
                (user_id, preference_id),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _row_to_record(row) if row is not None else None

    async def create(
        self,
        *,
        user_id: int,
        preference_id: str,
        preference_type: str,
        source: str,
        evidence_json: str,
        preference_json: str,
        status: str,
        version: int = LEARNED_PREFERENCE_VERSION,
        now: datetime | None = None,
    ) -> LearnedPreferenceRecord:
        """Write a new row once. Sets lifecycle timestamps implied by status."""
        now_iso = _utc_now_iso(now)
        accepted_at = now_iso if status in ("accepted", "active") else None
        revoked_at = now_iso if status == "revoked" else None
        archived_at = now_iso if status == "archived" else None
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_learned_preferences_table(db)
                await db.execute(
                    """
                    INSERT INTO learned_preferences (
                        id, user_id, type, status, source, version,
                        evidence_json, preference_json, created_at,
                        accepted_at, revoked_at, archived_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        preference_id,
                        user_id,
                        preference_type,
                        status,
                        source,
                        version,
                        evidence_json,
                        preference_json,
                        now_iso,
                        accepted_at,
                        revoked_at,
                        archived_at,
                    ),
                )
                await db.commit()
        except aiosqlite.IntegrityError as exc:
            # A row for this (user_id, id) already exists: it was already
            # decided in another session/tab.
            raise LearnedPreferenceNotAvailableError(preference_id) from exc
        except aiosqlite.Error as exc:
            raise LearnedPreferencePersistenceError(
                "Failed to create learned preference"
            ) from exc
        record = await self.get(user_id, preference_id)
        if record is None:
            raise LearnedPreferencePersistenceError(
                "Saved learned preference is invalid"
            )
        return record

    async def transition(
        self,
        *,
        user_id: int,
        preference_id: str,
        target_status: str,
        allowed_from: tuple[str, ...],
        now: datetime | None = None,
    ) -> LearnedPreferenceRecord:
        """Guarded status transition. Only status + one timestamp column change."""
        timestamp_column = _TIMESTAMP_COLUMNS.get(target_status)
        if timestamp_column is None:
            raise ValueError(f"Unsupported transition: {target_status}")
        placeholders = ", ".join("?" for _ in allowed_from)
        now_iso = _utc_now_iso(now)
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_learned_preferences_table(db)
                cursor = await db.execute(
                    f"""
                    UPDATE learned_preferences
                    SET status = ?,
                        {timestamp_column} = COALESCE({timestamp_column}, ?)
                    WHERE user_id = ? AND id = ? AND status IN ({placeholders})
                    """,
                    (
                        target_status,
                        now_iso,
                        user_id,
                        preference_id,
                        *allowed_from,
                    ),
                )
                changed = cursor.rowcount
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise LearnedPreferencePersistenceError(
                "Failed to update learned preference"
            ) from exc
        if changed == 0:
            existing = await self.get(user_id, preference_id)
            if existing is None:
                raise LearnedPreferenceNotFoundError(preference_id)
            raise LearnedPreferenceNotAvailableError(existing.status)
        record = await self.get(user_id, preference_id)
        if record is None:
            raise LearnedPreferenceNotFoundError(preference_id)
        return record

    async def set_last_review_generation(
        self,
        *,
        user_id: int,
        preference_id: str,
        generation: int,
    ) -> LearnedPreferenceRecord:
        """Persist dismissed review cohort. Does not change preference status."""
        if generation < 0:
            raise ValueError("generation must be >= 0")
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_learned_preferences_table(db)
                cursor = await db.execute(
                    """
                    UPDATE learned_preferences
                    SET last_review_generation = ?
                    WHERE user_id = ? AND id = ? AND status = 'active'
                    """,
                    (generation, user_id, preference_id),
                )
                changed = cursor.rowcount
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise LearnedPreferencePersistenceError(
                "Failed to dismiss learned preference review"
            ) from exc
        if changed == 0:
            existing = await self.get(user_id, preference_id)
            if existing is None:
                raise LearnedPreferenceNotFoundError(preference_id)
            raise LearnedPreferenceNotAvailableError(existing.status)
        record = await self.get(user_id, preference_id)
        if record is None:
            raise LearnedPreferenceNotFoundError(preference_id)
        return record