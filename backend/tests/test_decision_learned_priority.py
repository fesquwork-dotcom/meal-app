from decision.engine import DecisionEngine
from decision.learned_preferences_context import (
    ActiveLearnedPreference,
    LearnedPreferencesContext,
)
from strategy.memory_context import ConfirmedMemorySignal, StrategyMemoryContext


LEARNED = LearnedPreferencesContext(
    version=1,
    enabled=True,
    prefer_familiar_meals=True,
    prefer_faster_meals=True,
    source_preferences=(
        ActiveLearnedPreference("prefer_familiar_meals", 1),
        ActiveLearnedPreference("prefer_fast_meals", 1),
    ),
)
MEMORY = StrategyMemoryContext(
    prefer_faster_meals=True,
    signals=(
        ConfirmedMemorySignal(
            signal_id="private-memory-id",
            signal_type="prefer_faster_meals",
            target_value="",
            target_label=None,
            confirmation_source="user",
        ),
    ),
)


def test_explicit_profile_false_vetoes_learned_values():
    result = DecisionEngine().evaluate(
        {
            "planning_preferences": {"prefer_familiar_meals": False},
            "cooking_preferences": {"prefer_faster_meals": False},
        },
        MEMORY,
        learned_context=LEARNED,
    )
    assert result.strategy.prefer_familiar_meals is False
    assert result.strategy.prefer_faster_meals is False
    assert result.decision.behavior.familiar_source == "profile"
    assert result.decision.cooking.preference_source == "profile"


def test_learned_faster_wins_memory_without_changing_limit():
    result = DecisionEngine().evaluate(
        {"cooktime": "medium"},
        MEMORY,
        learned_context=LEARNED,
    )
    assert result.strategy.prefer_faster_meals is True
    assert result.strategy.cooking_time_limit == 45
    assert result.decision.cooking.preference_source == "learned_preference"
    memory_decision = next(
        item
        for item in result.build_result.applied_memory.decisions
        if item.signal_type == "prefer_faster_meals"
    )
    assert memory_decision.applied is False
    assert (
        memory_decision.reason_code
        == "LEARNED_PREFERENCE_REDUNDANT_WITH_MEMORY"
    )


def test_profile_true_is_winner_and_learned_is_redundant():
    result = DecisionEngine().evaluate(
        {
            "planning_preferences": {"prefer_familiar_meals": True},
            "cooking_preferences": {"prefer_faster_meals": True},
        },
        MEMORY,
        learned_context=LEARNED,
    )
    snapshot = result.build_result.applied_learned_preferences
    assert snapshot is not None
    assert all(not item.applied for item in snapshot.decisions)
    assert all(
        item.reason_code == "LEARNED_PREFERENCE_REDUNDANT_WITH_PROFILE"
        for item in snapshot.decisions
    )
