"""Builds applied settings summaries for strategy API responses."""

from __future__ import annotations

import logging

from strategy.applied_behavior import (
    AppliedBehaviorSettingsResponse,
    AppliedBehaviorSnapshot,
    BEHAVIOR_AVAILABILITY_FRICTION_APPLIED,
)
from strategy.applied_cooking import (
    AppliedCookingPreference,
    AppliedCookingSettingsResponse,
    AppliedSettingsResponse,
    CookingPreferenceSource,
)
from strategy.applied_planning import (
    AppliedPlanningPreferences,
    AppliedPlanningSettingsResponse,
)

logger = logging.getLogger(__name__)


def _build_behavior_settings(
    applied_behavior: AppliedBehaviorSnapshot | None,
) -> AppliedBehaviorSettingsResponse | None:
    if applied_behavior is None or not applied_behavior.decisions:
        return None

    applied_count = sum(1 for decision in applied_behavior.decisions if decision.applied)
    ignored_count = sum(1 for decision in applied_behavior.decisions if not decision.applied)
    availability_applied = any(
        decision.applied and BEHAVIOR_AVAILABILITY_FRICTION_APPLIED == decision.reason_code
        for decision in applied_behavior.decisions
    )

    if applied_count == 0 and not availability_applied:
        return AppliedBehaviorSettingsResponse(
            applied_count=0,
            ignored_count=ignored_count,
            availability_preferences_applied=False,
        )

    return AppliedBehaviorSettingsResponse(
        applied_count=applied_count,
        ignored_count=ignored_count,
        availability_preferences_applied=availability_applied,
    )


def infer_legacy_cooking_source(strategy: WeeklyStrategy) -> CookingPreferenceSource:
    """Infers source for strategies saved before applied cooking snapshots."""
    if strategy.strategy_version < 2:
        return "inferred"
    return "inferred"


def build_applied_settings_response(
    strategy: WeeklyStrategy,
    applied_cooking: AppliedCookingPreference | None,
    applied_behavior: AppliedBehaviorSnapshot | None = None,
    applied_planning: AppliedPlanningPreferences | None = None,
) -> AppliedSettingsResponse:
    if applied_cooking is not None:
        source = applied_cooking.source
        prefer_faster = applied_cooking.prefer_faster_meals
    else:
        source = infer_legacy_cooking_source(strategy)
        prefer_faster = strategy.prefer_faster_meals
        logger.info(
            "applied_cooking_source_inferred strategy_version=%s prefer_faster_meals=%s",
            strategy.strategy_version,
            prefer_faster,
        )

    behavior = _build_behavior_settings(applied_behavior)
    planning = _build_planning_settings(strategy, applied_planning)

    return AppliedSettingsResponse(
        cooking=AppliedCookingSettingsResponse(
            cooking_time_limit=strategy.cooking_time_limit,
            prefer_faster_meals=prefer_faster,
            preference_source=source,
        ),
        behavior=behavior,
        planning=planning,
    )


def _build_planning_settings(
    strategy: WeeklyStrategy,
    applied_planning: AppliedPlanningPreferences | None,
) -> AppliedPlanningSettingsResponse | None:
    if applied_planning is not None:
        if not applied_planning.prefer_familiar_meals:
            return None
        return AppliedPlanningSettingsResponse(
            prefer_familiar_meals=applied_planning.prefer_familiar_meals,
            familiar_meals_source=applied_planning.familiar_meals_source,
        )
    if strategy.strategy_version >= 4 and strategy.prefer_familiar_meals:
        return AppliedPlanningSettingsResponse(
            prefer_familiar_meals=strategy.prefer_familiar_meals,
            familiar_meals_source="inferred",
        )
    return None
