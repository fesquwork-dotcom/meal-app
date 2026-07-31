"""Read-only data consistency checks for local diagnostics (Sprint 9.5)."""

from __future__ import annotations

import aiosqlite

import database
from strategy.records import StrategyStatus


async def check_user_data_consistency(user_id: int) -> dict[str, object]:
    """Return allowlisted consistency codes. Never auto-repairs."""
    issues: list[str] = []
    db_path = database.resolve_database_path()

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        cursor = await db.execute(
            """
            SELECT COUNT(*) AS cnt FROM weekly_strategies
            WHERE user_id = ? AND status = ?
            """,
            (user_id, StrategyStatus.ACTIVE.value),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row and int(row["cnt"]) > 1:
            issues.append("MULTIPLE_ACTIVE_STRATEGIES")

        cursor = await db.execute(
            """
            SELECT COUNT(*) AS cnt FROM menu_plans
            WHERE user_id = ? AND status = 'active'
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row and int(row["cnt"]) > 1:
            issues.append("MULTIPLE_ACTIVE_MENU_PLANS")

        cursor = await db.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM menu_plans mp
            LEFT JOIN weekly_strategies ws
              ON ws.id = mp.strategy_id AND ws.user_id = mp.user_id
            WHERE mp.user_id = ? AND ws.id IS NULL
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row and int(row["cnt"]) > 0:
            issues.append("ORPHAN_MENU_PLAN")

        cursor = await db.execute(
            """
            SELECT COUNT(*) AS cnt FROM learned_preferences
            WHERE user_id = ?
              AND status = 'active'
              AND accepted_at IS NULL
            """,
            (user_id,),
        )
        row = await cursor.fetchone()
        await cursor.close()
        if row and int(row["cnt"]) > 0:
            issues.append("INVALID_LEARNED_PREFERENCE_LIFECYCLE")

        cursor = await db.execute(
            """
            SELECT last_review_generation FROM learned_preferences
            WHERE user_id = ? AND last_review_generation IS NOT NULL
            """,
            (user_id,),
        )
        rows = await cursor.fetchall()
        await cursor.close()
        for item in rows:
            value = item["last_review_generation"]
            if isinstance(value, int) and value > 3:
                issues.append("INVALID_REVIEW_GENERATION")
                break

    return {
        "status": "ok" if not issues else "issues_found",
        "issues": issues,
    }


async def lifecycle_summary_counts(user_id: int) -> dict[str, int]:
    """Privacy-safe counts for the diagnostics debug bundle."""
    db_path = database.resolve_database_path()
    counts = {
        "strategies": 0,
        "menu_plans": 0,
        "memory_events": 0,
        "learning_recommendations": 0,
        "learned_preferences": 0,
    }
    async with aiosqlite.connect(db_path) as db:
        for key, table in (
            ("strategies", "weekly_strategies"),
            ("menu_plans", "menu_plans"),
            ("memory_events", "memory_events"),
            ("learning_recommendations", "learning_recommendations"),
            ("learned_preferences", "learned_preferences"),
        ):
            try:
                cursor = await db.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE user_id = ?",
                    (user_id,),
                )
                row = await cursor.fetchone()
                await cursor.close()
                counts[key] = int(row[0]) if row else 0
            except aiosqlite.Error:
                counts[key] = 0
    return counts
