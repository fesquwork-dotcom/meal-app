"""Decision Engine resolve/evaluate behavior parity with legacy StrategyBuilder rules."""

from datetime import datetime, timezone

from decision.engine import DecisionEngine
from decision.versions import DECISION_VERSION, STRATEGY_VERSION_WITH_DECISIONS
from strategy.behavior_context import StrategyBehaviorContext
from strategy.memory_context import StrategyMemoryContext


FIXED_NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)


def test_engine_evaluate_matches_budget_rules():
    engine = DecisionEngine(clock=lambda: FIXED_NOW)
    result = engine.evaluate(
        {
            "goal": "budget",
            "days": 7,
            "cooktime": "medium",
            "budget": 3500.0,
        }
    )

    assert result.decision.decision_version == DECISION_VERSION
    assert result.strategy.strategy_version == STRATEGY_VERSION_WITH_DECISIONS
    assert result.strategy.repeat_breakfasts is True
    assert result.strategy.shopping_days == [1, 4]
    assert result.strategy.cook_days == [1, 3, 5, 7]
    assert result.decision.budget.weekly_budget == 3500.0
    assert result.decision.budget.daily_budget == 500.0
    assert result.decision.cooking.batch_allowed is True


def test_engine_resolve_empty_inputs_uses_defaults():
    engine = DecisionEngine(clock=lambda: FIXED_NOW)
    decision = engine.resolve({})

    assert decision.goal == "home"
    assert decision.days == 5
    assert decision.cooking.time_limit == 45
    assert decision.protein.preferred == ["any"]
    assert decision.memory.active_signal_count == 0
    assert decision.behavior.confirmed_behavior_count == 0


def test_engine_is_deterministic_for_same_inputs():
    engine = DecisionEngine(clock=lambda: FIXED_NOW)
    profile = {"goal": "healthy", "days": 5, "cooktime": "fast"}
    first = engine.evaluate(profile, StrategyMemoryContext.empty(), StrategyBehaviorContext.empty())
    second = engine.evaluate(profile, StrategyMemoryContext.empty(), StrategyBehaviorContext.empty())

    assert first.strategy.model_dump(exclude={"generated_at"}) == second.strategy.model_dump(
        exclude={"generated_at"}
    )
    assert first.decision.reason_codes == second.decision.reason_codes
