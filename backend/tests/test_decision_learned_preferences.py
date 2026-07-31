from decision.engine import DecisionEngine
from decision.learned_preferences_context import (
    ActiveLearnedPreference,
    LearnedPreferencesContext,
)


def _context(*types: str) -> LearnedPreferencesContext:
    return LearnedPreferencesContext(
        version=1,
        enabled=True,
        prefer_familiar_meals=True
        if "prefer_familiar_meals" in types
        else None,
        prefer_faster_meals=True if "prefer_fast_meals" in types else None,
        source_preferences=tuple(
            ActiveLearnedPreference(kind, 1) for kind in sorted(types)
        ),
    )


def test_learned_familiar_changes_only_familiar_decision():
    engine = DecisionEngine()
    baseline = engine.evaluate({})
    learned = engine.evaluate(
        {}, learned_context=_context("prefer_familiar_meals")
    )
    assert baseline.strategy.prefer_familiar_meals is False
    assert learned.strategy.prefer_familiar_meals is True
    assert (
        baseline.strategy.model_dump(
            exclude={"generated_at", "prefer_familiar_meals"}
        )
        == learned.strategy.model_dump(
            exclude={"generated_at", "prefer_familiar_meals"}
        )
    )


def test_learned_faster_does_not_change_cooking_time_limit():
    learned = DecisionEngine().evaluate(
        {"cooktime": "slow"},
        learned_context=_context("prefer_fast_meals"),
    )
    assert learned.strategy.prefer_faster_meals is True
    assert learned.strategy.cooking_time_limit == 90
    assert learned.decision.cooking.preference_source == "learned_preference"
