"""Shared fixtures for decision trace tests."""

from __future__ import annotations

from behavior.constants import BehaviorInsightStatus, BehaviorInsightType
from behavior.records import BehaviorInsightRecord
from memory.constants import SignalType
from strategy.behavior_context import (
    StrategyBehaviorContext,
    build_strategy_behavior_context,
)
from strategy.memory_context import ConfirmedMemorySignal, StrategyMemoryContext


def memory_faster(*, source: str = "automatic") -> StrategyMemoryContext:
    signal = ConfirmedMemorySignal(
        signal_id="sig-faster-1",
        signal_type=SignalType.PREFER_FASTER_MEALS.value,
        target_value="",
        target_label="Быстрее",
        confirmation_source=source,
    )
    return StrategyMemoryContext(prefer_faster_meals=True, signals=(signal,))


def memory_avoid(target: str, *, source: str = "automatic") -> StrategyMemoryContext:
    signal = ConfirmedMemorySignal(
        signal_id="sig-avoid-1",
        signal_type=SignalType.AVOID_INGREDIENT.value,
        target_value=target,
        target_label=target,
        confirmation_source=source,
    )
    return StrategyMemoryContext(avoided_ingredients=(target,), signals=(signal,))


def behavior_availability(target: str) -> StrategyBehaviorContext:
    record = BehaviorInsightRecord(
        id="insight-availability-1",
        user_id=1,
        insight_key=f"{BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION.value}:{target}",
        insight_type=BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION.value,
        target_key=target,
        target_label=target,
        status=BehaviorInsightStatus.CONFIRMED.value,
        confidence=1.0,
        evidence_count=2,
        evidence_window_days=90,
        rule_version=1,
        first_seen_at="2026-07-01T10:00:00+00:00",
        last_seen_at="2026-07-01T10:00:00+00:00",
        created_at="2026-07-01T10:00:00+00:00",
        updated_at="2026-07-01T10:00:00+00:00",
        confirmed_at="2026-07-01T10:00:00+00:00",
        dismissed_at=None,
        expires_at=None,
    )
    return build_strategy_behavior_context([record])
