from decision.learned_preferences_context import (
    ActiveLearnedPreference,
    LearnedPreferencesContext,
)
from strategy.behavior_context import StrategyBehaviorContext
from strategy.builder import StrategyBuilder
from strategy.memory_context import StrategyMemoryContext


def test_preview_generate_builder_parity_for_same_server_context():
    context = LearnedPreferencesContext(
        version=1,
        enabled=True,
        prefer_familiar_meals=True,
        prefer_faster_meals=True,
        source_preferences=(
            ActiveLearnedPreference("prefer_familiar_meals", 1),
            ActiveLearnedPreference("prefer_fast_meals", 1),
        ),
    )
    profile = {"goal": "home", "cooktime": "medium"}
    memory = StrategyMemoryContext.empty()
    behavior = StrategyBehaviorContext.empty()
    builder = StrategyBuilder()
    preview = builder.build_with_reasons_from_inputs(
        profile, memory, behavior, context
    )
    generate = builder.build_with_reasons_from_inputs(
        profile, memory, behavior, context
    )
    assert preview.strategy == generate.strategy
    assert preview.decision_context == generate.decision_context
    assert preview.decision_trace == generate.decision_trace
    assert (
        preview.applied_learned_preferences
        == generate.applied_learned_preferences
    )


def test_current_strategy_snapshot_does_not_change_when_context_changes():
    builder = StrategyBuilder()
    current = builder.build_with_reasons_from_inputs({})
    context = LearnedPreferencesContext(
        version=1,
        enabled=True,
        prefer_familiar_meals=True,
        prefer_faster_meals=None,
        source_preferences=(
            ActiveLearnedPreference("prefer_familiar_meals", 1),
        ),
    )
    _future = builder.build_with_reasons_from_inputs(
        {}, learned_context=context
    )
    assert current.strategy.prefer_familiar_meals is False
    assert current.strategy.model_dump()["prefer_familiar_meals"] is False
