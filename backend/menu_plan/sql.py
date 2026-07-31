"""SQL helpers that run inside a caller-owned transaction.

These functions exist so the generation pipeline can persist the strategy and
its initial MenuPlan snapshot in ONE transaction: a strategy is never written
without its plan, and a plan is never written without its strategy.
"""

from __future__ import annotations

import aiosqlite

from menu_plan.records import MenuPlanChangeType, MenuPlanStatus


async def supersede_active_menu_plans(
    db: aiosqlite.Connection, *, user_id: int, now: str
) -> None:
    await db.execute(
        """
        UPDATE menu_plans
        SET status = ?, superseded_at = ?, updated_at = ?
        WHERE user_id = ? AND status = ?
        """,
        (
            MenuPlanStatus.SUPERSEDED.value,
            now,
            now,
            user_id,
            MenuPlanStatus.ACTIVE.value,
        ),
    )


async def insert_initial_menu_plan(
    db: aiosqlite.Connection,
    *,
    menu_plan_id: str,
    user_id: int,
    strategy_id: str,
    plan_json: str,
    now: str,
) -> None:
    """Insert the immutable original snapshot plus revision 1."""
    await db.execute(
        """
        INSERT INTO menu_plans (
            id, user_id, strategy_id, status, current_revision,
            original_plan_json, created_at, updated_at, superseded_at
        ) VALUES (?, ?, ?, ?, 1, ?, ?, ?, NULL)
        """,
        (
            menu_plan_id,
            user_id,
            strategy_id,
            MenuPlanStatus.ACTIVE.value,
            plan_json,
            now,
            now,
        ),
    )
    await db.execute(
        """
        INSERT INTO menu_plan_revisions (
            menu_plan_id, revision, change_type, plan_json,
            changed_meal_ids_json, created_at
        ) VALUES (?, 1, ?, ?, NULL, ?)
        """,
        (menu_plan_id, MenuPlanChangeType.INITIAL.value, plan_json, now),
    )
