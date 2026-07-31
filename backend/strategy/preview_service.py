"""Orchestrates strategy preview without Claude or persistence."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone

from decision.user_explanation import (
    MAX_PREVIEW_EXPLANATIONS,
    build_decision_explanations,
)
from decision.learned_preferences_context import LearnedPreferencesContext
from strategy.applied_settings import build_applied_settings_response
from strategy.behavior_context import StrategyBehaviorContext
from strategy.builder import StrategyBuilder
from strategy.conflict_targets import ConflictResolutionTarget, build_detected_conflict
from strategy.conflicts import detect_strategy_conflicts
from strategy.context import ProfileContext
from strategy.explanation import build_strategy_explanation
from strategy.memory_context import StrategyMemoryContext
from strategy.preview_models import AppliedMemorySummary, StrategyPreviewResponse
from strategy.preview_token import issue_preview_token
from strategy.versions import STRATEGY_PREVIEW_VERSION

logger = logging.getLogger(__name__)


class StrategyPreviewService:
    def __init__(self, builder: StrategyBuilder | None = None) -> None:
        self._builder = builder or StrategyBuilder()

    def build_preview(
        self,
        profile: dict[str, object],
        memory_context: StrategyMemoryContext,
        behavior_context: StrategyBehaviorContext,
        learned_context: LearnedPreferencesContext | None = None,
        *,
        user_id: int,
        profile_revision: int,
        plan_start_date: str,
        memory_unavailable: bool = False,
        behavior_unavailable: bool = False,
        learned_preferences_unavailable: bool = False,
    ) -> StrategyPreviewResponse:
        started = time.perf_counter()
        learned_context = learned_context or LearnedPreferencesContext.empty()
        profile_context = ProfileContext.from_profile(profile)
        blocking_detected, warnings_detected = detect_strategy_conflicts(
            profile_context,
            memory_context,
            profile_revision=profile_revision,
            preview_version=STRATEGY_PREVIEW_VERSION,
        )

        if memory_unavailable:
            from strategy.preview_models import ConflictResolutionOption

            memory_warning = build_detected_conflict(
                code="MEMORY_CONTEXT_UNAVAILABLE",
                title="Память временно недоступна",
                description=(
                    "Не удалось загрузить сохранённые предпочтения. "
                    "План будет создан только по профилю."
                ),
                severity="warning",
                field="memory",
                options=[
                    ConflictResolutionOption(
                        action="continue_with_warning",
                        label="Продолжить",
                        description=None,
                    )
                ],
                target=ConflictResolutionTarget(profile_field="memory"),
                profile_revision=profile_revision,
                preview_version=STRATEGY_PREVIEW_VERSION,
                priority=80,
            )
            warnings_detected = [memory_warning, *warnings_detected]

        if behavior_unavailable:
            logger.info("behavior_context_unavailable user_id=%s", user_id)

        blocking = [item.conflict for item in blocking_detected]
        warnings = [item.conflict for item in warnings_detected]

        token, expires_at = issue_preview_token(
            user_id=user_id,
            profile=profile,
            profile_revision=profile_revision,
            plan_start_date=plan_start_date,
            memory_context=memory_context,
            behavior_context=behavior_context,
            learned_context=learned_context,
            memory_unavailable=memory_unavailable,
            behavior_unavailable=behavior_unavailable,
            learned_preferences_unavailable=learned_preferences_unavailable,
        )
        expires_iso = datetime.fromtimestamp(expires_at, tz=timezone.utc).replace(
            microsecond=0
        ).isoformat()

        if blocking:
            logger.info(
                "strategy_preview_conflict conflict_count=%s warning_count=%s duration_ms=%s",
                len(blocking),
                len(warnings),
                int((time.perf_counter() - started) * 1000),
            )
            return StrategyPreviewResponse(
                status="conflict",
                preview_version=STRATEGY_PREVIEW_VERSION,
                conflicts=blocking,
                warnings=warnings,
                preview_token=token,
                preview_expires_at=expires_iso,
                memory_unavailable=memory_unavailable,
            )

        if learned_context.enabled:
            build_result = self._builder.build_with_reasons_from_inputs(
                profile, memory_context, behavior_context, learned_context
            )
        else:
            # Exact Sprint 9.1 call path while rollout is disabled.
            build_result = self._builder.build_with_reasons_from_inputs(
                profile, memory_context, behavior_context
            )
        strategy = build_result.strategy
        explanation = build_strategy_explanation(
            strategy,
            reason_codes=build_result.reason_codes,
            source="recorded",
        )
        decision_explanations = (
            build_decision_explanations(
                build_result.decision_trace,
                strategy=strategy,
                max_explanations=MAX_PREVIEW_EXPLANATIONS,
            )
            if build_result.decision_trace is not None
            else None
        )
        memory_summary = _build_memory_summary(build_result.applied_memory)
        applied_settings = build_applied_settings_response(
            strategy,
            build_result.applied_cooking_preference,
            build_result.applied_behavior,
            build_result.applied_planning_preferences,
        )

        behavior_applied = (
            applied_settings.behavior.applied_count if applied_settings.behavior else 0
        )
        behavior_ignored = (
            applied_settings.behavior.ignored_count if applied_settings.behavior else 0
        )
        logger.info(
            "strategy_preview_ready warning_count=%s applied_count=%s behavior_applied_count=%s "
            "behavior_ignored_count=%s duration_ms=%s token_issued=true preference_source=%s",
            len(warnings),
            memory_summary.applied_count,
            behavior_applied,
            behavior_ignored,
            int((time.perf_counter() - started) * 1000),
            applied_settings.cooking.preference_source,
        )

        return StrategyPreviewResponse(
            status="ready",
            preview_version=STRATEGY_PREVIEW_VERSION,
            strategy=strategy,
            explanation=explanation,
            decision_explanations=decision_explanations,
            decision_trace=build_result.decision_trace,
            conflicts=[],
            warnings=warnings,
            memory_summary=memory_summary,
            applied_settings=applied_settings,
            preview_token=token,
            preview_expires_at=expires_iso,
            memory_unavailable=memory_unavailable,
        )


def _build_memory_summary(applied_memory) -> AppliedMemorySummary:
    if applied_memory is None:
        return AppliedMemorySummary()

    applied_count = sum(1 for decision in applied_memory.decisions if decision.applied)
    ignored_count = sum(1 for decision in applied_memory.decisions if not decision.applied)
    types = sorted(
        {
            decision.signal_type
            for decision in applied_memory.decisions
            if decision.applied
        }
    )
    return AppliedMemorySummary(
        has_applied_signals=applied_count > 0,
        applied_count=applied_count,
        ignored_count=ignored_count,
        types=types,
    )
