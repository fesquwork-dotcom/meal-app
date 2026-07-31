"""Deterministic builder that maps DecisionContext into WeeklyStrategy.

Decision-making lives in ``decision.DecisionEngine``. This class only assembles
the strategy snapshot. Profile/memory/behavior arguments are accepted solely as a
compatibility façade that delegates to DecisionEngine — no local rule logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Callable, overload

from strategy.behavior_context import StrategyBehaviorContext
from strategy.build_result import StrategyBuildResult
from strategy.memory_context import StrategyMemoryContext
from strategy.models import WeeklyStrategy
from decision.learned_preferences_context import LearnedPreferencesContext

if TYPE_CHECKING:
    from decision.context import DecisionContext

ClockFn = Callable[[], datetime]


class StrategyBuilder:
    """Builds WeeklyStrategy from a pre-computed DecisionContext."""

    def __init__(self, clock: ClockFn | None = None) -> None:
        self._clock = clock

    @overload
    def build(self, decision: DecisionContext) -> WeeklyStrategy: ...

    @overload
    def build(
        self,
        profile: dict[str, object] | None = None,
        memory_context: StrategyMemoryContext | None = None,
        behavior_context: StrategyBehaviorContext | None = None,
        learned_context: LearnedPreferencesContext | None = None,
    ) -> WeeklyStrategy: ...

    def build(
        self,
        profile_or_decision: dict[str, object] | DecisionContext | None = None,
        memory_context: StrategyMemoryContext | None = None,
        behavior_context: StrategyBehaviorContext | None = None,
        learned_context: LearnedPreferencesContext | None = None,
    ) -> WeeklyStrategy:
        return self.build_with_reasons(
            profile_or_decision, memory_context, behavior_context, learned_context
        ).strategy

    @overload
    def build_with_reasons(self, decision: DecisionContext) -> StrategyBuildResult: ...

    @overload
    def build_with_reasons(
        self,
        profile: dict[str, object] | None = None,
        memory_context: StrategyMemoryContext | None = None,
        behavior_context: StrategyBehaviorContext | None = None,
        learned_context: LearnedPreferencesContext | None = None,
    ) -> StrategyBuildResult: ...

    def build_with_reasons(
        self,
        profile_or_decision: dict[str, object] | DecisionContext | None = None,
        memory_context: StrategyMemoryContext | None = None,
        behavior_context: StrategyBehaviorContext | None = None,
        learned_context: LearnedPreferencesContext | None = None,
    ) -> StrategyBuildResult:
        from decision.builder import DecisionBuilder
        from decision.context import DecisionContext as DecisionContextType
        from decision.engine import DecisionEngine

        if isinstance(profile_or_decision, DecisionContextType):
            return DecisionBuilder().build(profile_or_decision)
        return DecisionEngine(clock=self._clock).evaluate(
            profile_or_decision, memory_context, behavior_context, learned_context
        ).build_result

    def build_from_inputs(
        self,
        profile: dict[str, object] | None,
        memory_context: StrategyMemoryContext | None = None,
        behavior_context: StrategyBehaviorContext | None = None,
        learned_context: LearnedPreferencesContext | None = None,
    ) -> WeeklyStrategy:
        return self.build_with_reasons_from_inputs(
            profile, memory_context, behavior_context, learned_context
        ).strategy

    def build_with_reasons_from_inputs(
        self,
        profile: dict[str, object] | None,
        memory_context: StrategyMemoryContext | None = None,
        behavior_context: StrategyBehaviorContext | None = None,
        learned_context: LearnedPreferencesContext | None = None,
    ) -> StrategyBuildResult:
        from decision.engine import DecisionEngine

        return DecisionEngine(clock=self._clock).evaluate(
            profile, memory_context, behavior_context, learned_context
        ).build_result
