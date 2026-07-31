"""Maps DecisionContext to WeeklyStrategy without consulting Profile/Memory/Behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

from decision.context import DecisionContext
from decision.trace_models import DecisionTrace
from strategy.applied_behavior import AppliedBehaviorSnapshot
from strategy.applied_cooking import AppliedCookingPreference
from strategy.applied_learned_preferences import AppliedLearnedPreferencesSnapshot
from strategy.applied_planning import AppliedPlanningPreferences
from strategy.build_result import StrategyBuildResult
from strategy.memory_context import AppliedMemorySnapshot
from strategy.models import WeeklyStrategy

if TYPE_CHECKING:
    from decision.resolver import ResolvedDecisionBundle


class DecisionBuilder:
    """Pure assembler: DecisionContext → WeeklyStrategy (+ recorded artifacts)."""

    def build(
        self,
        decision: DecisionContext,
        *,
        applied_memory: AppliedMemorySnapshot | None = None,
        applied_cooking_preference: AppliedCookingPreference | None = None,
        applied_behavior: AppliedBehaviorSnapshot | None = None,
        applied_planning_preferences: AppliedPlanningPreferences | None = None,
        applied_learned_preferences: AppliedLearnedPreferencesSnapshot | None = None,
        decision_trace: DecisionTrace | None = None,
    ) -> StrategyBuildResult:
        strategy = WeeklyStrategy(
            strategy_version=decision.strategy_version,
            goal=decision.goal,  # type: ignore[arg-type]
            days=decision.days,
            budget=decision.budget.weekly_budget,
            meal_types=decision.meal_types,  # type: ignore[arg-type]
            meals_per_day=decision.meals_per_day,
            cook_days=list(decision.cooking.cook_days),
            shopping_days=list(decision.shopping.shopping_days),
            leftovers_enabled=decision.cooking.leftovers_enabled,
            repeat_breakfasts=decision.cooking.repeat_breakfasts,
            repeat_lunches=decision.cooking.repeat_lunches,
            repeat_dinners=decision.cooking.repeat_dinners,
            preferred_proteins=list(decision.protein.preferred),  # type: ignore[arg-type]
            excluded_products=list(decision.excluded_products),
            cooking_time_limit=decision.cooking.time_limit,
            prefer_faster_meals=decision.cooking.prefer_faster,
            availability_avoid_products=list(decision.behavior.availability_avoid_products),
            prefer_familiar_meals=decision.behavior.prefer_familiar,
            generated_at=decision.generated_at,
        )
        return StrategyBuildResult(
            strategy=strategy,
            reason_codes=list(decision.reason_codes),
            applied_memory=applied_memory,
            applied_cooking_preference=applied_cooking_preference,
            applied_behavior=applied_behavior,
            applied_planning_preferences=applied_planning_preferences,
            applied_learned_preferences=applied_learned_preferences,
            decision_context=decision,
            decision_trace=decision_trace,
        )

    def build_from_bundle(self, bundle: "ResolvedDecisionBundle") -> StrategyBuildResult:
        return self.build(
            bundle.decision,
            applied_memory=bundle.applied_memory,
            applied_cooking_preference=bundle.applied_cooking_preference,
            applied_behavior=bundle.applied_behavior,
            applied_planning_preferences=bundle.applied_planning_preferences,
            applied_learned_preferences=bundle.applied_learned_preferences,
            decision_trace=bundle.trace,
        )
