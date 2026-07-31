"""Async orchestration: load durable plan variants, run the pure engine."""

from __future__ import annotations

import logging

from menu_plan.repository import MenuPlanRepository
from plan_delta.engine import build_plan_delta

logger = logging.getLogger(__name__)


class PlanDeltaService:
    def __init__(self, repository: MenuPlanRepository | None = None) -> None:
        self._repository = repository or MenuPlanRepository()

    async def get_delta(self, menu_plan_id: str, user_id: int) -> dict[str, object]:
        """Delta between the immutable original and the current revision.

        Raises MenuPlanNotFoundError for missing/foreign plans (handled by
        the API layer); malformed stored JSON degrades to status "none".
        """
        record = await self._repository.get_by_id(menu_plan_id, user_id)
        original = self._repository.parse_plan(record.original_plan_json)
        revision = await self._repository.get_revision(
            record.id, record.current_revision
        )
        current = self._repository.parse_plan(
            revision.plan_json if revision is not None else None
        )
        if original is None or current is None:
            logger.warning("plan_delta_unavailable menu_plan_id=%s", record.id)
            return {"status": "none"}

        delta = build_plan_delta(original, current)
        available = sum(
            1 for metric in delta.metrics if metric.status == "available"
        )
        logger.info(
            "plan_delta_computed menu_plan_id=%s revision=%s available_metrics=%s",
            record.id,
            record.current_revision,
            available,
        )
        return {
            "status": "ready",
            "menu_plan_id": record.id,
            "revision": record.current_revision,
            "has_replacements": record.current_revision > 1,
            "delta": delta.model_dump(mode="json"),
        }
