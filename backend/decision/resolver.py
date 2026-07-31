"""Resolves Profile/Memory/Behavior into a DecisionContext (no WeeklyStrategy)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from decision.context import DecisionContext
from decision.learned_preferences_context import LearnedPreferencesContext
from decision.models import (
    BehaviorDecision,
    BudgetDecision,
    CookingDecision,
    DecisionReason,
    MemoryDecision,
    ProteinDecision,
    ShoppingDecision,
)
from decision.trace_builder import TraceBuildInputs, build_decision_trace
from decision.trace_models import DecisionTrace
from decision.versions import DECISION_VERSION, STRATEGY_VERSION_WITH_DECISIONS
from strategy.applied_behavior import AppliedBehaviorSnapshot
from strategy.applied_cooking import AppliedCookingPreference
from strategy.applied_learned_preferences import (
    AppliedLearnedPreferenceDecision,
    AppliedLearnedPreferencesSnapshot,
)
from strategy.applied_planning import AppliedPlanningPreferences
from strategy.behavior_apply import apply_behavior_insights
from strategy.behavior_context import StrategyBehaviorContext
from strategy.context import ProfileContext
from strategy.cooking_preference import resolve_effective_faster_preference
from strategy.memory_apply import apply_memory_signals
from strategy.memory_context import AppliedMemorySnapshot, StrategyMemoryContext
from strategy.planning_preference import (
    familiar_meals_reason_codes,
    resolve_effective_familiar_meals_preference,
)
from strategy.reason_codes import collect_reason_codes
from strategy.resolvers import (
    resolve_budget,
    resolve_cook_days,
    resolve_cooking_time_limit,
    resolve_days,
    resolve_excluded_products,
    resolve_generated_at,
    resolve_goal,
    resolve_leftovers_enabled,
    resolve_meal_types_list,
    resolve_meals_per_day,
    resolve_preferred_proteins,
    resolve_repeat_breakfasts,
    resolve_repeat_dinners,
    resolve_repeat_lunches,
    resolve_shopping_days,
)

ClockFn = Callable[[], datetime]


def _build_applied_learned_snapshot(
    profile: ProfileContext,
    learned: LearnedPreferencesContext,
) -> AppliedLearnedPreferencesSnapshot:
    decisions: list[AppliedLearnedPreferenceDecision] = []
    for source in learned.source_preferences:
        if source.preference_type == "prefer_familiar_meals":
            profile_value = profile.prefer_familiar_meals
            if profile_value is None:
                applied = True
                reason = "LEARNED_FAMILIAR_MEALS_APPLIED"
            elif profile_value is True:
                applied = False
                reason = "LEARNED_PREFERENCE_REDUNDANT_WITH_PROFILE"
            else:
                applied = False
                reason = "LEARNED_PREFERENCE_IGNORED_PROFILE_PRIORITY"
            decisions.append(
                AppliedLearnedPreferenceDecision(
                    preference_type="prefer_familiar_meals",
                    applied=applied,
                    reason_code=reason,
                    decision_key="planning.prefer_familiar_meals",
                )
            )
        elif source.preference_type == "prefer_fast_meals":
            profile_value = profile.prefer_faster_meals
            if profile_value is None:
                applied = True
                reason = "LEARNED_FASTER_MEALS_APPLIED"
            elif profile_value is True:
                applied = False
                reason = "LEARNED_PREFERENCE_REDUNDANT_WITH_PROFILE"
            else:
                applied = False
                reason = "LEARNED_PREFERENCE_IGNORED_PROFILE_PRIORITY"
            decisions.append(
                AppliedLearnedPreferenceDecision(
                    preference_type="prefer_fast_meals",
                    applied=applied,
                    reason_code=reason,
                    decision_key="cooking.prefer_faster",
                )
            )
    return AppliedLearnedPreferencesSnapshot(
        enabled=learned.enabled,
        decisions=decisions,
    )


@dataclass(frozen=True)
class ResolvedDecisionBundle:
    """DecisionContext plus applied snapshots needed for StrategyBuildResult."""

    decision: DecisionContext
    applied_memory: AppliedMemorySnapshot | None
    applied_cooking_preference: AppliedCookingPreference | None
    applied_behavior: AppliedBehaviorSnapshot | None
    applied_planning_preferences: AppliedPlanningPreferences | None
    applied_learned_preferences: AppliedLearnedPreferencesSnapshot
    trace: DecisionTrace | None = None


class DecisionResolver:
    """Sole place that interprets Profile, Memory, and Behavior into decisions."""

    def __init__(self, clock: ClockFn | None = None) -> None:
        self._clock = clock

    def resolve(
        self,
        profile: dict[str, object] | None,
        memory_context: StrategyMemoryContext | None = None,
        behavior_context: StrategyBehaviorContext | None = None,
        learned_context: LearnedPreferencesContext | None = None,
    ) -> DecisionContext:
        return self.resolve_bundle(
            profile, memory_context, behavior_context, learned_context
        ).decision

    def resolve_bundle(
        self,
        profile: dict[str, object] | None,
        memory_context: StrategyMemoryContext | None = None,
        behavior_context: StrategyBehaviorContext | None = None,
        learned_context: LearnedPreferencesContext | None = None,
    ) -> ResolvedDecisionBundle:
        context = ProfileContext.from_profile(profile)
        memory_context = memory_context or StrategyMemoryContext.empty()
        behavior_context = behavior_context or StrategyBehaviorContext.empty()
        learned_context = learned_context or LearnedPreferencesContext.empty()
        now = self._clock() if self._clock else None

        meal_types = resolve_meal_types_list(context)
        meals_per_day = resolve_meals_per_day(context)
        days = resolve_days(context)
        goal = resolve_goal(context)
        weekly_budget = resolve_budget(context)
        daily_budget = weekly_budget / days if days > 0 else weekly_budget

        base_excluded = resolve_excluded_products(context)
        base_proteins = resolve_preferred_proteins(context)
        base_cook_limit = resolve_cooking_time_limit(context)

        memory_result = apply_memory_signals(
            profile_context=context,
            memory_context=memory_context,
            base_excluded=base_excluded,
            base_preferred_proteins=base_proteins,
            base_cooking_time_limit=base_cook_limit,
            learned_prefer_faster=learned_context.prefer_faster_meals,
        )

        behavior_result = apply_behavior_insights(
            profile_context=context,
            memory_context=memory_context,
            behavior_context=behavior_context,
            effective_excluded_products=memory_result.excluded_products,
        )

        familiar_effective = resolve_effective_familiar_meals_preference(
            context,
            learned_context.prefer_familiar_meals,
        )
        familiar_reason_codes = familiar_meals_reason_codes(familiar_effective)

        cook_days = resolve_cook_days(context)
        shopping_days = resolve_shopping_days(context)
        leftovers_enabled = resolve_leftovers_enabled(context)
        all_days = list(range(1, days + 1))
        batch_allowed = cook_days != all_days or leftovers_enabled

        fresh_products_days = (
            list(shopping_days[1:]) if len(shopping_days) > 1 else list(shopping_days)
        )

        generated_at = resolve_generated_at(context, now=now)
        effective_faster = resolve_effective_faster_preference(
            context,
            memory_context,
            learned_context.prefer_faster_meals,
        )

        budget_priority = "budget" if goal == "budget" else "standard"
        blocked_proteins = [
            protein
            for protein in base_proteins
            if protein not in memory_result.preferred_proteins and protein != "any"
        ]

        applied_cooking = AppliedCookingPreference(
            prefer_faster_meals=memory_result.prefer_faster_meals,
            source=effective_faster.source,
            profile_value=context.prefer_faster_meals,
        )
        applied_behavior: AppliedBehaviorSnapshot | None = None
        if behavior_result.applied_behavior.decisions:
            applied_behavior = behavior_result.applied_behavior

        applied_planning = AppliedPlanningPreferences(
            prefer_familiar_meals=familiar_effective.prefer_familiar_meals,
            familiar_meals_source=familiar_effective.source,
            profile_value=familiar_effective.profile_value,
        )
        applied_learned = _build_applied_learned_snapshot(
            context,
            learned_context,
        )

        memory_preferences = sorted(
            {
                decision.signal_type
                for decision in memory_result.snapshot.decisions
                if decision.applied
            }
        )

        repeat_breakfasts = resolve_repeat_breakfasts(context)
        repeat_lunches = resolve_repeat_lunches(context)
        repeat_dinners = resolve_repeat_dinners(context)

        from strategy.models import WeeklyStrategy

        provisional = WeeklyStrategy(
            strategy_version=STRATEGY_VERSION_WITH_DECISIONS,
            goal=goal,
            days=days,
            budget=weekly_budget,
            meal_types=meal_types,  # type: ignore[arg-type]
            meals_per_day=meals_per_day,
            cook_days=cook_days,
            shopping_days=shopping_days,
            leftovers_enabled=leftovers_enabled,
            repeat_breakfasts=repeat_breakfasts,
            repeat_lunches=repeat_lunches,
            repeat_dinners=repeat_dinners,
            preferred_proteins=memory_result.preferred_proteins,  # type: ignore[arg-type]
            excluded_products=memory_result.excluded_products,
            cooking_time_limit=memory_result.cooking_time_limit,
            prefer_faster_meals=memory_result.prefer_faster_meals,
            availability_avoid_products=list(behavior_result.availability_avoid_products),
            prefer_familiar_meals=familiar_effective.prefer_familiar_meals,
            generated_at=generated_at,
        )

        reason_codes = collect_reason_codes(
            context,
            provisional,
            memory_reason_codes=memory_result.memory_reason_codes,
            behavior_reason_codes=list(behavior_result.reason_codes),
            planning_reason_codes=familiar_reason_codes,
        )

        decision = DecisionContext(
            decision_version=DECISION_VERSION,
            strategy_version=STRATEGY_VERSION_WITH_DECISIONS,
            goal=goal,
            days=days,
            meal_types=meal_types,
            meals_per_day=meals_per_day,
            generated_at=generated_at,
            excluded_products=list(memory_result.excluded_products),
            budget=BudgetDecision(
                daily_budget=daily_budget,
                weekly_budget=weekly_budget,
                priority=budget_priority,
                reasons=(
                    DecisionReason(
                        code="BUDGET_FROM_PROFILE",
                        source="profile",
                        priority=4,
                        description="Weekly budget taken from profile",
                    ),
                ),
            ),
            cooking=CookingDecision(
                time_limit=memory_result.cooking_time_limit,
                prefer_faster=memory_result.prefer_faster_meals,
                cook_days=list(cook_days),
                batch_allowed=batch_allowed,
                leftovers_enabled=leftovers_enabled,
                repeat_breakfasts=repeat_breakfasts,
                repeat_lunches=repeat_lunches,
                repeat_dinners=repeat_dinners,
                preference_source=effective_faster.source,
                profile_prefer_faster=context.prefer_faster_meals,
                cooktime_band=context.cooktime,
                reasons=tuple(
                    DecisionReason(
                        code=code,
                        source="memory"
                        if code.startswith("MEMORY_")
                        else ("profile" if code.startswith("PROFILE_") else "rule"),
                        priority=5,
                        description=code,
                    )
                    for code in memory_result.memory_reason_codes
                    if "FASTER" in code or code.startswith("PROFILE_FASTER")
                ),
            ),
            protein=ProteinDecision(
                allowed=list(memory_result.preferred_proteins),
                preferred=list(memory_result.preferred_proteins),
                blocked=blocked_proteins,
            ),
            shopping=ShoppingDecision(
                shopping_days=list(shopping_days),
                fresh_products_days=fresh_products_days,
            ),
            behavior=BehaviorDecision(
                prefer_familiar=familiar_effective.prefer_familiar_meals,
                availability_avoid_products=list(behavior_result.availability_avoid_products),
                confirmed_behavior_count=len(behavior_context.insights),
                familiar_source=familiar_effective.source,
                familiar_profile_value=familiar_effective.profile_value,
                reasons=tuple(
                    DecisionReason(
                        code=code,
                        source="behavior",
                        priority=11,
                        description=code,
                    )
                    for code in behavior_result.reason_codes
                ),
            ),
            memory=MemoryDecision(
                confirmed_preferences=memory_preferences,
                temporary_avoids=list(memory_result.snapshot.avoided_ingredients),
                active_signal_count=len(memory_context.signals),
                prefer_faster_from_memory=memory_result.prefer_faster_meals
                and effective_faster.source == "memory",
                reasons=tuple(
                    DecisionReason(
                        code=code,
                        source="memory",
                        priority=10,
                        description=code,
                    )
                    for code in memory_result.memory_reason_codes
                ),
            ),
            reason_codes=tuple(reason_codes),
        )

        behavior_ignored_count = sum(
            1
            for item in behavior_result.applied_behavior.decisions
            if not item.applied
        )
        trace = build_decision_trace(
            TraceBuildInputs(
                profile_raw=dict(profile or {}),
                context=context,
                memory_context=memory_context,
                behavior_context=behavior_context,
                learned_context=learned_context,
                memory_result=memory_result,
                availability_avoid_count=len(behavior_result.availability_avoid_products),
                behavior_ignored_count=behavior_ignored_count,
                effective_faster=effective_faster,
                familiar_effective=familiar_effective,
                goal=goal,
                days=days,
                weekly_budget=weekly_budget,
                daily_budget=daily_budget,
                base_cook_limit=base_cook_limit,
                cook_days=list(cook_days),
                shopping_days=list(shopping_days),
                leftovers_enabled=leftovers_enabled,
                batch_allowed=batch_allowed,
                repeat_breakfasts=repeat_breakfasts,
                repeat_lunches=repeat_lunches,
                repeat_dinners=repeat_dinners,
            )
        )

        return ResolvedDecisionBundle(
            decision=decision,
            applied_memory=memory_result.snapshot,
            applied_cooking_preference=applied_cooking,
            applied_behavior=applied_behavior,
            applied_planning_preferences=applied_planning,
            applied_learned_preferences=applied_learned,
            trace=trace,
        )
