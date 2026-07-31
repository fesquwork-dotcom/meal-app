"""Durable MenuPlan persistence (Sprint 7.2).

Rules enforced here:
- the original generated plan (revision 1) is immutable;
- every later state is an append-only revision;
- the current plan is the latest validated revision;
- appends are guarded by optimistic concurrency (expected revision / CAS);
- ownership is checked on every read and write.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

import aiosqlite

import database
from menu_plan.exceptions import (
    MenuPlanConcurrencyError,
    MenuPlanNotFoundError,
    MenuPlanPersistenceError,
)
from menu_plan.records import (
    MenuPlanChangeType,
    MenuPlanRecord,
    MenuPlanRevisionRecord,
    MenuPlanStatus,
)

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_record(row: aiosqlite.Row) -> MenuPlanRecord:
    return MenuPlanRecord(
        id=row["id"],
        user_id=row["user_id"],
        strategy_id=row["strategy_id"],
        status=row["status"],
        current_revision=row["current_revision"],
        original_plan_json=row["original_plan_json"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        superseded_at=row["superseded_at"],
    )


def _row_to_revision(row: aiosqlite.Row) -> MenuPlanRevisionRecord:
    return MenuPlanRevisionRecord(
        menu_plan_id=row["menu_plan_id"],
        revision=row["revision"],
        change_type=row["change_type"],
        plan_json=row["plan_json"],
        changed_meal_ids_json=row["changed_meal_ids_json"],
        created_at=row["created_at"],
    )


class MenuPlanRepository:
    async def get_active_for_user(self, user_id: int) -> MenuPlanRecord | None:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_menu_plan_tables(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM menu_plans
                WHERE user_id = ? AND status = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (user_id, MenuPlanStatus.ACTIVE.value),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _row_to_record(row) if row is not None else None

    async def list_for_user(
        self,
        user_id: int,
        *,
        limit: int,
        before: tuple[str, str] | None = None,
    ) -> list[MenuPlanRecord]:
        """Newest-first page of plans; `before` is the (created_at, id) cursor.

        Fetches limit + 1 rows so the caller can tell whether a next page
        exists without a second query.
        """
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_menu_plan_tables(db)
            db.row_factory = aiosqlite.Row
            if before is None:
                cursor = await db.execute(
                    """
                    SELECT * FROM menu_plans
                    WHERE user_id = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (user_id, int(limit) + 1),
                )
            else:
                cursor = await db.execute(
                    """
                    SELECT * FROM menu_plans
                    WHERE user_id = ?
                      AND (created_at < ? OR (created_at = ? AND id < ?))
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (user_id, before[0], before[0], before[1], int(limit) + 1),
                )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_row_to_record(row) for row in rows]

    async def get_by_id(self, menu_plan_id: str, user_id: int) -> MenuPlanRecord:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_menu_plan_tables(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM menu_plans WHERE id = ? AND user_id = ?",
                (menu_plan_id, user_id),
            )
            row = await cursor.fetchone()
            await cursor.close()
        if row is None:
            # Ownership violations are indistinguishable from missing plans.
            raise MenuPlanNotFoundError(f"Menu plan not found: {menu_plan_id}")
        return _row_to_record(row)

    async def get_revision(
        self, menu_plan_id: str, revision: int
    ) -> MenuPlanRevisionRecord | None:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM menu_plan_revisions
                WHERE menu_plan_id = ? AND revision = ?
                """,
                (menu_plan_id, revision),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _row_to_revision(row) if row is not None else None

    async def append_revision(
        self,
        *,
        menu_plan_id: str,
        user_id: int,
        expected_revision: int,
        plan_json: str,
        change_type: MenuPlanChangeType,
        changed_meal_ids: list[str] | None = None,
    ) -> int:
        """Append the next validated state; CAS on the current revision."""
        if change_type == MenuPlanChangeType.INITIAL:
            raise MenuPlanPersistenceError("Initial revision is write-once")
        db_path = database.resolve_database_path()
        now = _utc_now_iso()
        new_revision = expected_revision + 1
        changed_json = (
            json.dumps(changed_meal_ids, ensure_ascii=False)
            if changed_meal_ids
            else None
        )
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_menu_plan_tables(db)
                await db.execute("BEGIN IMMEDIATE")
                cursor = await db.execute(
                    """
                    UPDATE menu_plans
                    SET current_revision = ?, updated_at = ?
                    WHERE id = ? AND user_id = ? AND current_revision = ?
                    """,
                    (new_revision, now, menu_plan_id, user_id, expected_revision),
                )
                updated = cursor.rowcount > 0
                await cursor.close()
                if not updated:
                    await db.rollback()
                    cursor = await db.execute(
                        "SELECT current_revision FROM menu_plans "
                        "WHERE id = ? AND user_id = ?",
                        (menu_plan_id, user_id),
                    )
                    row = await cursor.fetchone()
                    await cursor.close()
                    if row is None:
                        raise MenuPlanNotFoundError(
                            f"Menu plan not found: {menu_plan_id}"
                        )
                    logger.info(
                        "menu_plan_revision_conflict menu_plan_id=%s "
                        "expected_revision=%s current_revision=%s",
                        menu_plan_id,
                        expected_revision,
                        row[0],
                    )
                    raise MenuPlanConcurrencyError(
                        "Menu plan was changed in another session"
                    )
                await db.execute(
                    """
                    INSERT INTO menu_plan_revisions (
                        menu_plan_id, revision, change_type, plan_json,
                        changed_meal_ids_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        menu_plan_id,
                        new_revision,
                        change_type.value,
                        plan_json,
                        changed_json,
                        now,
                    ),
                )
                await db.commit()
        except (MenuPlanNotFoundError, MenuPlanConcurrencyError):
            raise
        except aiosqlite.Error as exc:
            logger.error(
                "menu_plan_revision_save_failed menu_plan_id=%s error=%s",
                menu_plan_id,
                exc,
            )
            raise MenuPlanPersistenceError(
                "Failed to append menu plan revision"
            ) from exc
        logger.info(
            "menu_plan_revision_saved menu_plan_id=%s revision=%s change_type=%s",
            menu_plan_id,
            new_revision,
            change_type.value,
        )
        return new_revision

    def parse_plan(self, plan_json: str | None) -> dict[str, object] | None:
        """Lenient parse for serving; malformed rows never break reads."""
        if not plan_json:
            return None
        try:
            parsed = json.loads(plan_json)
        except json.JSONDecodeError:
            logger.warning("menu_plan_unavailable reason=malformed_json")
            return None
        if not isinstance(parsed, dict):
            logger.warning("menu_plan_unavailable reason=not_object")
            return None
        return parsed
