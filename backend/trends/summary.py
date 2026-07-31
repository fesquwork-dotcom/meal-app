"""Async orchestration: load history, run the pure engine, project for API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from trends.api_models import TrendSummaryResponse, to_trend_summary_response
from trends.engine import build_trend_summary
from trends.repository import TrendRepository

logger = logging.getLogger(__name__)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class TrendService:
    def __init__(self, repository: TrendRepository | None = None) -> None:
        self._repository = repository or TrendRepository()

    async def get_trend_summary(self, user_id: int) -> TrendSummaryResponse:
        observations = await self._repository.load_week_observations(user_id)
        accepted = await self._repository.load_accepted_recommendations(user_id)
        summary = build_trend_summary(
            observations, accepted, generated_at=_utc_now_iso()
        )
        logger.info(
            "trend_summary_generated weeks=%s confidence=%s established_metrics=%s",
            summary.confidence.weeks,
            summary.confidence.status,
            sum(
                1
                for metric in summary.metrics
                if metric.confidence.status == "established"
            ),
        )
        return to_trend_summary_response(summary)
