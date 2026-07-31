"""Atomic per-user data reset for local QA (Sprint 9.5)."""

from __future__ import annotations

import logging
from typing import Literal

import aiosqlite

import database
from dev_tools.guards import assert_dev_tools_enabled

logger = logging.getLogger(__name__)

ResetMode = Literal["history_only", "full_user"]

_HISTORY_TABLES = (
    "menu_plans",
    "weekly_strategies",
    "memory_events",
    "preference_signals",
    "behavior_insights",
    "learning_recommendations",
    "learned_preferences",
)

# menu_plan_revisions has no user_id column of its own; it is scoped through
# its parent menu_plans row and must be deleted before that row disappears.
_MENU_PLAN_REVISIONS_DELETE_SQL = (
    "DELETE FROM menu_plan_revisions "
    "WHERE menu_plan_id IN (SELECT id FROM menu_plans WHERE user_id = ?)"
)


class DevResetService:
    async def reset_current_user(
        self, user_id: int, *, mode: ResetMode
    ) -> dict[str, object]:
        assert_dev_tools_enabled()
        if mode not in {"history_only", "full_user"}:
            raise ValueError(f"Unsupported reset mode: {mode}")

        db_path = database.resolve_database_path()
        deleted: dict[str, int] = {}

        async with aiosqlite.connect(db_path) as db:
            # Ensure schema exists (idempotent).
            await database._ensure_menu_plan_tables(db)
            await database._ensure_learning_recommendations_table(db)
            await database._ensure_learned_preferences_table(db)
            await db.execute(database.CREATE_BEHAVIOR_INSIGHTS_SQL)
            await db.execute(database.CREATE_MEMORY_EVENTS_SQL)
            await db.execute(database.CREATE_PREFERENCE_SIGNALS_SQL)
            await db.execute(database.CREATE_WEEKLY_STRATEGIES_SQL)

            try:
                await db.execute("BEGIN")
                cursor = await db.execute(_MENU_PLAN_REVISIONS_DELETE_SQL, (user_id,))
                deleted["menu_plan_revisions"] = int(cursor.rowcount or 0)
                await cursor.close()

                for table in _HISTORY_TABLES:
                    cursor = await db.execute(
                        f"DELETE FROM {table} WHERE user_id = ?",
                        (user_id,),
                    )
                    deleted[table] = int(cursor.rowcount or 0)
                    await cursor.close()

                if mode == "full_user":
                    cursor = await db.execute(
                        "DELETE FROM profiles WHERE user_id = ?",
                        (user_id,),
                    )
                    deleted["profiles"] = int(cursor.rowcount or 0)
                    await cursor.close()

                await db.commit()
            except Exception:
                await db.rollback()
                logger.warning("dev_reset_failed mode=%s", mode)
                raise

        logger.info(
            "dev_user_reset mode=%s tables=%s",
            mode,
            ",".join(f"{k}:{v}" for k, v in deleted.items()),
        )
        return {
            "mode": mode,
            "deleted": deleted,
            "status": "ok",
        }
