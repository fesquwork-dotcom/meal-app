from decision.engine import DecisionEngine
from decision.learned_preferences_context import (
    ActiveLearnedPreference,
    LearnedPreferencesContext,
)


def test_disabled_context_has_exact_sprint_9_1_behavior():
    profile = {
        "goal": "budget",
        "days": 7,
        "cooktime": "medium",
        "planning_preferences": {"prefer_familiar_meals": None},
        "cooking_preferences": {"prefer_faster_meals": None},
    }
    engine = DecisionEngine()
    legacy = engine.evaluate(profile)
    disabled = engine.evaluate(
        profile,
        learned_context=LearnedPreferencesContext.empty(enabled=False),
    )
    assert legacy == disabled


def test_only_mapped_fields_change_when_enabled():
    profile = {"goal": "home", "cooktime": "medium"}
    engine = DecisionEngine()
    baseline = engine.evaluate(profile)
    enabled = engine.evaluate(
        profile,
        learned_context=LearnedPreferencesContext(
            version=1,
            enabled=True,
            prefer_familiar_meals=True,
            prefer_faster_meals=True,
            source_preferences=(
                ActiveLearnedPreference("prefer_familiar_meals", 1),
                ActiveLearnedPreference("prefer_fast_meals", 1),
            ),
        ),
    )
    excluded = {
        "generated_at",
        "prefer_familiar_meals",
        "prefer_faster_meals",
    }
    assert baseline.strategy.model_dump(exclude=excluded) == enabled.strategy.model_dump(
        exclude=excluded
    )
