"""Decision Engine — resolve inputs, then assemble WeeklyStrategy."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from decision.builder import DecisionBuilder
from decision.context import DecisionContext
from decision.learned_preferences_context import LearnedPreferencesContext
from decision.resolver import DecisionResolver
from strategy.behavior_context import StrategyBehaviorContext
from strategy.build_result import StrategyBuildResult
from strategy.memory_context import StrategyMemoryContext
from strategy.models import WeeklyStrategy

ClockFn = Callable[[], datetime]


@dataclass(frozen=True)
class DecisionEvaluationResult:
    decision: DecisionContext
    build_result: StrategyBuildResult

    @property
    def strategy(self) -> WeeklyStrategy:
        return self.build_result.strategy

    @property
    def reason_codes(self) -> list[str]:
        return self.build_result.reason_codes

    @property
    def trace(self):
        return self.build_result.decision_trace


class DecisionEngine:
    """Public entry for Decision Intelligence: inputs → DecisionContext → Strategy."""

    def __init__(self, clock: ClockFn | None = None) -> None:
        self._resolver = DecisionResolver(clock=clock)
        self._builder = DecisionBuilder()

    def resolve(
        self,
        profile: dict[str, object] | None,
        memory_context: StrategyMemoryContext | None = None,
        behavior_context: StrategyBehaviorContext | None = None,
        learned_context: LearnedPreferencesContext | None = None,
    ) -> DecisionContext:
        return self._resolver.resolve(
            profile, memory_context, behavior_context, learned_context
        )

    def build(self, decision: DecisionContext) -> StrategyBuildResult:
        return self._builder.build(decision)

    def evaluate(
        self,
        profile: dict[str, object] | None,
        memory_context: StrategyMemoryContext | None = None,
        behavior_context: StrategyBehaviorContext | None = None,
        learned_context: LearnedPreferencesContext | None = None,
    ) -> DecisionEvaluationResult:
        bundle = self._resolver.resolve_bundle(
            profile, memory_context, behavior_context, learned_context
        )
        build_result = self._builder.build_from_bundle(bundle)
        return DecisionEvaluationResult(decision=bundle.decision, build_result=build_result)
