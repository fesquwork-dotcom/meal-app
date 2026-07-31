"""Decision / strategy version compatibility."""

from datetime import datetime, timezone

from decision.engine import DecisionEngine
from decision.versions import DECISION_VERSION, STRATEGY_VERSION_WITH_DECISIONS
from strategy.builder import StrategyBuilder
from strategy.models import WeeklyStrategy
from strategy.repository import SUPPORTED_STRATEGY_VERSIONS


FIXED_NOW = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)


def test_new_strategies_stamp_decision_and_strategy_versions():
    evaluation = DecisionEngine(clock=lambda: FIXED_NOW).evaluate({"days": 3})
    assert evaluation.decision.decision_version == DECISION_VERSION
    assert evaluation.strategy.strategy_version == STRATEGY_VERSION_WITH_DECISIONS
    assert STRATEGY_VERSION_WITH_DECISIONS in SUPPORTED_STRATEGY_VERSIONS


def test_legacy_strategy_versions_remain_readable():
    for version in (1, 2, 3, 4):
        strategy = WeeklyStrategy(
            strategy_version=version,
            goal="home",
            days=3,
            budget=3000.0,
            meal_types=["breakfast", "lunch", "dinner"],
            meals_per_day=3,
            cook_days=[1, 2, 3],
            shopping_days=[1],
            leftovers_enabled=True,
            repeat_breakfasts=False,
            repeat_lunches=False,
            repeat_dinners=False,
            preferred_proteins=["any"],
            excluded_products=[],
            cooking_time_limit=45,
            generated_at="2026-01-01T00:00:00+00:00",
        )
        restored = WeeklyStrategy.from_json(strategy.to_json())
        assert restored.strategy_version == version


def test_strategy_builder_from_decision_does_not_change_values():
    engine = DecisionEngine(clock=lambda: FIXED_NOW)
    decision = engine.resolve({"goal": "healthy", "days": 5, "cooktime": "fast"})
    from_engine = engine.build(decision).strategy
    from_builder = StrategyBuilder(clock=lambda: FIXED_NOW).build(decision)

    assert from_engine.model_dump() == from_builder.model_dump()


def test_profile_facade_and_decision_path_identical():
    builder = StrategyBuilder(clock=lambda: FIXED_NOW)
    profile = {"goal": "budget", "days": 7, "cooktime": "medium", "budget": 4000.0}

    via_facade = builder.build(profile)
    via_decision = builder.build(DecisionEngine(clock=lambda: FIXED_NOW).resolve(profile))

    assert via_facade.model_dump(exclude={"generated_at"}) == via_decision.model_dump(
        exclude={"generated_at"}
    )
