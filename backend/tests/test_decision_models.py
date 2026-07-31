"""Unit tests for DecisionContext models and serialization."""

from decision.context import DecisionContext
from decision.models import (
    BehaviorDecision,
    BudgetDecision,
    CookingDecision,
    DecisionReason,
    MemoryDecision,
    ProteinDecision,
    ShoppingDecision,
)
from decision.versions import DECISION_VERSION, STRATEGY_VERSION_WITH_DECISIONS


def _sample_decision() -> DecisionContext:
    return DecisionContext(
        decision_version=DECISION_VERSION,
        strategy_version=STRATEGY_VERSION_WITH_DECISIONS,
        goal="home",
        days=5,
        meal_types=["breakfast", "lunch", "dinner"],
        meals_per_day=3,
        generated_at="2026-07-14T12:00:00+00:00",
        excluded_products=["орехи"],
        budget=BudgetDecision(
            daily_budget=600.0,
            weekly_budget=3000.0,
            priority="standard",
            reasons=(
                DecisionReason(
                    code="BUDGET_FROM_PROFILE",
                    source="profile",
                    priority=4,
                    description="from profile",
                ),
            ),
        ),
        cooking=CookingDecision(
            time_limit=45,
            prefer_faster=False,
            cook_days=[1, 2, 3, 4, 5],
            batch_allowed=True,
            leftovers_enabled=True,
            repeat_breakfasts=False,
            repeat_lunches=False,
            repeat_dinners=False,
            preference_source="default",
            cooktime_band="medium",
        ),
        protein=ProteinDecision(allowed=["chicken"], preferred=["chicken"], blocked=[]),
        shopping=ShoppingDecision(shopping_days=[1], fresh_products_days=[1]),
        behavior=BehaviorDecision(
            prefer_familiar=False,
            availability_avoid_products=[],
            confirmed_behavior_count=0,
        ),
        memory=MemoryDecision(
            confirmed_preferences=[],
            temporary_avoids=[],
            active_signal_count=0,
        ),
        reason_codes=("GOAL_HOME", "COOKING_TIME_LIMIT_MEDIUM"),
    )


def test_decision_context_round_trip_json():
    original = _sample_decision()
    restored = DecisionContext.from_json(original.to_json())

    assert restored is not None
    assert restored.decision_version == DECISION_VERSION
    assert restored.strategy_version == STRATEGY_VERSION_WITH_DECISIONS
    assert restored.goal == "home"
    assert restored.budget.weekly_budget == 3000.0
    assert restored.cooking.time_limit == 45
    assert restored.protein.preferred == ["chicken"]
    assert restored.excluded_products == ["орехи"]
    assert "GOAL_HOME" in restored.reason_codes


def test_decision_reason_preserved():
    original = _sample_decision()
    restored = DecisionContext.from_json(original.to_json())
    assert restored is not None
    assert restored.budget.reasons[0].code == "BUDGET_FROM_PROFILE"
    assert restored.budget.reasons[0].source == "profile"


def test_decision_context_from_malformed_json_returns_none():
    assert DecisionContext.from_json("{not-json") is None
    assert DecisionContext.from_json(None) is None
    assert DecisionContext.from_json("[]") is None
