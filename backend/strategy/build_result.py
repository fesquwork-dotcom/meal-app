"""Result of deterministic strategy construction including decision trace."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from strategy.applied_behavior import AppliedBehaviorSnapshot
from strategy.applied_planning import AppliedPlanningPreferences
from strategy.applied_cooking import AppliedCookingPreference
from strategy.applied_learned_preferences import AppliedLearnedPreferencesSnapshot
from strategy.memory_context import AppliedMemorySnapshot
from strategy.models import WeeklyStrategy

if TYPE_CHECKING:
    from decision.context import DecisionContext
    from decision.trace_models import DecisionTrace


@dataclass(frozen=True)
class StrategyBuildResult:
    strategy: WeeklyStrategy
    reason_codes: list[str]
    applied_memory: AppliedMemorySnapshot | None = None
    applied_cooking_preference: AppliedCookingPreference | None = None
    applied_behavior: AppliedBehaviorSnapshot | None = None
    applied_planning_preferences: AppliedPlanningPreferences | None = None
    applied_learned_preferences: AppliedLearnedPreferencesSnapshot | None = None
    decision_context: "DecisionContext | None" = None
    decision_trace: "DecisionTrace | None" = None
