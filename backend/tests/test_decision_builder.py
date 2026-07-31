"""DecisionBuilder maps DecisionContext to WeeklyStrategy without re-deciding."""

from decision.builder import DecisionBuilder
from decision.context import DecisionContext
from decision.models import (
    BehaviorDecision,
    BudgetDecision,
    CookingDecision,
    MemoryDecision,
    ProteinDecision,
    ShoppingDecision,
)
from decision.versions import STRATEGY_VERSION_WITH_DECISIONS


def test_decision_builder_assembles_strategy_fields():
    decision = DecisionContext(
        strategy_version=STRATEGY_VERSION_WITH_DECISIONS,
        goal="healthy",
        days=7,
        meal_types=["breakfast", "dinner"],
        meals_per_day=2,
        generated_at="2026-07-14T12:00:00+00:00",
        excluded_products=["лактоза"],
        budget=BudgetDecision(daily_budget=500.0, weekly_budget=3500.0, priority="standard"),
        cooking=CookingDecision(
            time_limit=20,
            prefer_faster=True,
            cook_days=[1, 2, 3, 4, 5, 6, 7],
            batch_allowed=False,
            leftovers_enabled=True,
            repeat_breakfasts=False,
            repeat_lunches=False,
            repeat_dinners=False,
            preference_source="profile",
            profile_prefer_faster=True,
            cooktime_band="fast",
        ),
        protein=ProteinDecision(allowed=["fish"], preferred=["fish"], blocked=[]),
        shopping=ShoppingDecision(shopping_days=[1], fresh_products_days=[1]),
        behavior=BehaviorDecision(
            prefer_familiar=True,
            availability_avoid_products=["киноа"],
            confirmed_behavior_count=1,
            familiar_source="profile",
            familiar_profile_value=True,
        ),
        memory=MemoryDecision(
            confirmed_preferences=["avoid_ingredient"],
            temporary_avoids=["гречка"],
            active_signal_count=1,
        ),
        reason_codes=("GOAL_HEALTHY", "COOKING_TIME_LIMIT_FAST"),
    )

    result = DecisionBuilder().build(decision)

    assert result.strategy.strategy_version == STRATEGY_VERSION_WITH_DECISIONS
    assert result.strategy.goal == "healthy"
    assert result.strategy.meal_types == ["breakfast", "dinner"]
    assert result.strategy.meals_per_day == 2
    assert result.strategy.prefer_faster_meals is True
    assert result.strategy.prefer_familiar_meals is True
    assert result.strategy.availability_avoid_products == ["киноа"]
    assert result.strategy.excluded_products == ["лактоза"]
    assert result.reason_codes == ["GOAL_HEALTHY", "COOKING_TIME_LIMIT_FAST"]
    assert result.decision_context is decision
