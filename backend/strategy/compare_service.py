"""Orchestrates strategy comparison without persistence or Claude (Sprint 5.24)."""

from __future__ import annotations

import logging
import time

from decision.user_explanation import build_decision_explanation_changes
from strategy.applied_settings import build_applied_settings_response
from strategy.behavior_context import StrategyBehaviorContext
from strategy.compare_models import StrategyCompareResponse
from strategy.exceptions import StrategyNotFoundError
from strategy.memory_context import StrategyMemoryContext
from decision.learned_preferences_context import LearnedPreferencesContext
from strategy.preview_service import StrategyPreviewService
from strategy.repository import StrategyRepository
from strategy.settings_diff import build_strategy_settings_diff
from strategy.settings_diff_models import ComparisonQuality, StrategySettingsDiff

logger = logging.getLogger(__name__)


class StrategyCompareService:
    def __init__(
        self,
        repository: StrategyRepository | None = None,
        preview_service: StrategyPreviewService | None = None,
    ) -> None:
        self._repository = repository or StrategyRepository()
        self._preview_service = preview_service or StrategyPreviewService()

    async def compare(
        self,
        *,
        user_id: int,
        strategy_id: str,
        profile: dict[str, object],
        profile_revision: int,
        plan_start_date: str,
        memory_context: StrategyMemoryContext,
        behavior_context: StrategyBehaviorContext,
        learned_context: LearnedPreferencesContext | None = None,
        memory_unavailable: bool = False,
        behavior_unavailable: bool = False,
        learned_preferences_unavailable: bool = False,
    ) -> StrategyCompareResponse:
        started = time.perf_counter()

        try:
            record = await self._repository.get_by_id(strategy_id, user_id)
        except StrategyNotFoundError:
            logger.info("strategy_compare_unavailable reason=strategy_not_found")
            raise

        current_strategy = self._repository.restore_weekly_strategy(record)
        current_trace = self._repository.load_decision_trace(record)
        applied_cooking = self._repository.load_applied_cooking_preference(record)
        applied_behavior = self._repository.load_applied_behavior(record)
        applied_planning = self._repository.load_applied_planning_preferences(record)
        applied_learned = self._repository.load_applied_learned_preferences(record)
        current_applied = build_applied_settings_response(
            current_strategy, applied_cooking, applied_behavior, applied_planning
        )
        comparison_quality: ComparisonQuality = (
            "partial"
            if applied_cooking is None or applied_learned is None
            else "exact"
        )

        preview = self._preview_service.build_preview(
            profile,
            memory_context,
            behavior_context,
            learned_context,
            user_id=user_id,
            profile_revision=profile_revision,
            plan_start_date=plan_start_date,
            memory_unavailable=memory_unavailable,
            behavior_unavailable=behavior_unavailable,
            learned_preferences_unavailable=learned_preferences_unavailable,
        )

        if preview.status != "ready" or preview.strategy is None:
            logger.info(
                "strategy_compare_conflict change_count=0 duration_ms=%s",
                int((time.perf_counter() - started) * 1000),
            )
            return StrategyCompareResponse(preview=preview, diff=None)

        diff = build_strategy_settings_diff(
            current_strategy,
            preview.strategy,
            current_applied_settings=current_applied,
            next_applied_settings=preview.applied_settings,
            comparison_quality=comparison_quality,
        )
        decision_changes = build_decision_explanation_changes(
            current_trace,
            preview.decision_trace,
            current_strategy=current_strategy,
            next_strategy=preview.strategy,
        )

        change_keys = [change.key for change in diff.changes]
        if diff.has_changes:
            logger.info(
                "strategy_compare_ready change_count=%s change_keys=%s comparison_quality=%s duration_ms=%s",
                len(diff.changes),
                change_keys,
                diff.comparison_quality,
                int((time.perf_counter() - started) * 1000),
            )
        else:
            logger.info(
                "strategy_compare_no_changes comparison_quality=%s duration_ms=%s",
                diff.comparison_quality,
                int((time.perf_counter() - started) * 1000),
            )

        return StrategyCompareResponse(
            preview=preview,
            diff=diff,
            decision_changes=decision_changes,
        )
