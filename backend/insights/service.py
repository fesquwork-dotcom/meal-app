"""Read-only orchestration for Insight Engine inputs.

There is intentionally no ``insights.repository``. This service reads through
existing repositories and passes domain models to the pure engine.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from insights.api_models import InsightSummaryResponse, to_insight_summary_response
from insights.engine import build_insight_summary
from insights.evidence import build_evidence_basis
from menu_plan.repository import MenuPlanRepository
from plan_delta.engine import build_plan_delta
from plan_delta.models import PlanDelta
from strategy.repository import StrategyRepository
from trends.engine import build_trend_summary
from trends.repository import TrendRepository

logger = logging.getLogger(__name__)

MAX_INSIGHT_DELTA_PLANS = 10


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class InsightService:
    def __init__(
        self,
        *,
        trend_repository: TrendRepository | None = None,
        menu_plan_repository: MenuPlanRepository | None = None,
        strategy_repository: StrategyRepository | None = None,
    ) -> None:
        self._trend_repository = trend_repository or TrendRepository()
        self._menu_plan_repository = menu_plan_repository or MenuPlanRepository()
        self._strategy_repository = strategy_repository or StrategyRepository()

    async def get_summary(self, user_id: int) -> InsightSummaryResponse:
        generated_at = _utc_now_iso()
        observations = await self._trend_repository.load_week_observations(user_id)
        accepted = await self._trend_repository.load_accepted_recommendations(user_id)
        trends = build_trend_summary(
            observations, accepted, generated_at=generated_at
        )

        latest = await self._strategy_repository.get_latest_finalized_for_user(
            user_id
        )
        outcomes = (
            self._strategy_repository.load_decision_outcomes(latest)
            if latest is not None
            else None
        )
        deltas = await self._load_plan_deltas(user_id)
        basis = build_evidence_basis(observations)
        summary = build_insight_summary(
            trends, outcomes, deltas, generated_at=generated_at, basis=basis
        )
        logger.info(
            "insight_summary_generated confirmed=%s insufficient=%s",
            sum(item.status == "confirmed" for item in summary.insights),
            sum(item.status == "insufficient_data" for item in summary.insights),
        )
        logger.info(
            "insight_evidence_generated coverage=%s weeks=%s outcomes=%s",
            summary.insights[0].evidence.coverage.status if summary.insights else "n/a",
            basis.evidence_weeks,
            basis.decision_outcomes,
        )
        return to_insight_summary_response(summary)

    async def _load_plan_deltas(self, user_id: int) -> list[PlanDelta]:
        records = await self._menu_plan_repository.list_for_user(
            user_id, limit=MAX_INSIGHT_DELTA_PLANS
        )
        deltas: list[PlanDelta] = []
        for record in records[:MAX_INSIGHT_DELTA_PLANS]:
            # Original=current is not evidence about replacement impact.
            if record.current_revision <= 1:
                continue
            original = self._menu_plan_repository.parse_plan(
                record.original_plan_json
            )
            revision = await self._menu_plan_repository.get_revision(
                record.id, record.current_revision
            )
            current = self._menu_plan_repository.parse_plan(
                revision.plan_json if revision is not None else None
            )
            if original is not None and current is not None:
                deltas.append(build_plan_delta(original, current))
        return deltas

