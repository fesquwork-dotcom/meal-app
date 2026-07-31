"""API-facing orchestration for durable menu plans."""

from __future__ import annotations

import logging

from menu_plan.records import MenuPlanRecord
from menu_plan.repository import MenuPlanRepository

logger = logging.getLogger(__name__)

# History pagination bounds (Sprint 7.3).
DEFAULT_HISTORY_PAGE_SIZE = 10
MAX_HISTORY_PAGE_SIZE = 20

_CURSOR_SEPARATOR = "~"


def encode_history_cursor(record: MenuPlanRecord) -> str:
    return f"{record.created_at}{_CURSOR_SEPARATOR}{record.id}"


def decode_history_cursor(cursor: str) -> tuple[str, str] | None:
    """Returns (created_at, id) or None for malformed cursors."""
    if not cursor or len(cursor) > 200:
        return None
    head, separator, tail = cursor.partition(_CURSOR_SEPARATOR)
    if not separator or not head or not tail:
        return None
    return head, tail


class MenuPlanService:
    def __init__(self, repository: MenuPlanRepository | None = None) -> None:
        self._repository = repository or MenuPlanRepository()

    async def get_current(self, user_id: int) -> dict[str, object]:
        record = await self._repository.get_active_for_user(user_id)
        if record is None:
            return {"status": "none"}
        return await self._serve_record(record)

    async def get_by_id(self, menu_plan_id: str, user_id: int) -> dict[str, object]:
        record = await self._repository.get_by_id(menu_plan_id, user_id)
        return await self._serve_record(record)

    async def get_original(
        self, menu_plan_id: str, user_id: int
    ) -> dict[str, object]:
        """Immutable initial snapshot (revision 1), read-only by design."""
        record = await self._repository.get_by_id(menu_plan_id, user_id)
        plan = self._repository.parse_plan(record.original_plan_json)
        if plan is None:
            logger.warning(
                "menu_plan_original_unavailable menu_plan_id=%s", record.id
            )
            return {"status": "none"}
        plan["strategy_id"] = record.strategy_id
        return {
            "status": "ready",
            "view": "original",
            "menu_plan_id": record.id,
            "revision": 1,
            "strategy_id": record.strategy_id,
            "plan_status": record.status,
            "has_replacements": record.current_revision > 1,
            "plan": plan,
        }

    async def get_history(
        self,
        user_id: int,
        *,
        cursor: tuple[str, str] | None = None,
        limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    ) -> dict[str, object]:
        """Compact newest-first summaries; never includes full plan JSON."""
        page_size = max(1, min(int(limit), MAX_HISTORY_PAGE_SIZE))
        records = await self._repository.list_for_user(
            user_id, limit=page_size, before=cursor
        )
        has_more = len(records) > page_size
        page = records[:page_size]
        items = [await self._build_summary(record) for record in page]
        next_cursor = (
            encode_history_cursor(page[-1]) if has_more and page else None
        )
        return {"items": items, "next_cursor": next_cursor}

    async def _build_summary(self, record: MenuPlanRecord) -> dict[str, object]:
        revision = await self._repository.get_revision(
            record.id, record.current_revision
        )
        plan = self._repository.parse_plan(
            revision.plan_json if revision is not None else None
        )
        days_plan = plan.get("days_plan") if plan is not None else None
        total_cost = plan.get("total_cost") if plan is not None else None
        return {
            "menu_plan_id": record.id,
            "plan_status": record.status,
            "created_at": record.created_at,
            "plan_start_date": (
                plan.get("plan_start_date") if plan is not None else None
            ),
            "days": len(days_plan) if isinstance(days_plan, list) else None,
            "total_cost": (
                total_cost if isinstance(total_cost, (int, float)) else None
            ),
            "summary": (
                plan.get("summary") if plan is not None else None
            ),
            "has_replacements": record.current_revision > 1,
        }

    async def _serve_record(self, record: MenuPlanRecord) -> dict[str, object]:
        revision = await self._repository.get_revision(
            record.id, record.current_revision
        )
        plan = self._repository.parse_plan(
            revision.plan_json if revision is not None else None
        )
        if plan is None:
            # Durable state exists but cannot be served; clients keep their
            # local cache instead of receiving a broken plan.
            logger.warning(
                "menu_plan_current_unavailable menu_plan_id=%s revision=%s",
                record.id,
                record.current_revision,
            )
            return {"status": "none"}
        plan["strategy_id"] = record.strategy_id
        return {
            "status": "ready",
            "view": "current",
            "menu_plan_id": record.id,
            "revision": record.current_revision,
            "strategy_id": record.strategy_id,
            "plan_status": record.status,
            "has_replacements": record.current_revision > 1,
            "plan": plan,
        }
