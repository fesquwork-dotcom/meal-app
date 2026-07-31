"""Sprint 9.2.1 — Faster Preference Resolution Hardening.

Bug fix, not full Sprint 9.1 behavioral parity: explicit Profile
prefer_faster_meals must survive an empty Memory context. cooking_time_limit
stays independent. API / token / Strategy schema are unchanged.
"""

from __future__ import annotations

from decision.engine import DecisionEngine
from decision.learned_preferences_context import (
    ActiveLearnedPreference,
    LearnedPreferencesContext,
)
from decision.user_explanation import build_decision_explanations
from memory.constants import SignalType
from strategy.context import ProfileContext
from strategy.cooking_preference import (
    PROFILE_FASTER_MEALS_DISABLED,
    PROFILE_FASTER_MEALS_PREFERENCE_APPLIED,
)
from strategy.memory_apply import apply_memory_signals
from strategy.memory_context import ConfirmedMemorySignal, StrategyMemoryContext
from strategy.resolvers import resolve_cooking_time_limit


def _entry(result, key: str):
    assert result.trace is not None
    return next(item for item in result.trace.entries if item.decision_key == key)


def _learned_faster() -> LearnedPreferencesContext:
    return LearnedPreferencesContext(
        version=1,
        enabled=True,
        prefer_familiar_meals=None,
        prefer_faster_meals=True,
        source_preferences=(ActiveLearnedPreference("prefer_fast_meals", 1),),
    )


def _memory_faster() -> StrategyMemoryContext:
    return StrategyMemoryContext(
        prefer_faster_meals=True,
        signals=(
            ConfirmedMemorySignal(
                signal_id="mem-faster",
                signal_type=SignalType.PREFER_FASTER_MEALS.value,
                target_value="",
                target_label=None,
                confirmation_source="user",
            ),
        ),
    )


def _apply(profile: dict, memory=None, learned_faster=None):
    context = ProfileContext.from_profile(profile)
    return apply_memory_signals(
        profile_context=context,
        memory_context=memory or StrategyMemoryContext.empty(),
        base_excluded=[],
        base_preferred_proteins=["any"],
        base_cooking_time_limit=resolve_cooking_time_limit(context),
        learned_prefer_faster=learned_faster,
    )


# --- Regression matrix (seven required scenarios) ---


def test_profile_true_empty_memory_keeps_preference_and_limit():
    profile = {
        "cooktime": "slow",
        "cooking_preferences": {"prefer_faster_meals": True},
    }
    applied = _apply(profile)
    assert applied.prefer_faster_meals is True
    assert applied.cooking_time_limit == 90
    assert PROFILE_FASTER_MEALS_PREFERENCE_APPLIED in applied.memory_reason_codes

    result = DecisionEngine().evaluate(profile)
    assert result.strategy.prefer_faster_meals is True
    assert result.strategy.cooking_time_limit == 90
    assert result.decision.cooking.preference_source == "profile"
    assert result.build_result.applied_cooking_preference is not None
    assert result.build_result.applied_cooking_preference.source == "profile"
    assert result.build_result.applied_cooking_preference.prefer_faster_meals is True
    assert result.build_result.applied_memory is not None
    assert result.build_result.applied_memory.prefer_faster_meals is True

    entry = _entry(result, "cooking.prefer_faster")
    assert entry.outcome.value is True
    assert entry.priority_winner == "profile"
    assert entry.confidence == "explicit"
    assert any(
        rule.rule_code == "PROFILE_FASTER_PREFERENCE" and rule.result == "applied"
        for rule in entry.applied_rules
    )


def test_profile_false_empty_memory_keeps_disabled():
    profile = {
        "cooktime": "medium",
        "cooking_preferences": {"prefer_faster_meals": False},
    }
    applied = _apply(profile)
    assert applied.prefer_faster_meals is False
    assert applied.cooking_time_limit == 45
    assert PROFILE_FASTER_MEALS_DISABLED in applied.memory_reason_codes

    result = DecisionEngine().evaluate(profile)
    assert result.strategy.prefer_faster_meals is False
    assert result.decision.cooking.preference_source == "profile"
    entry = _entry(result, "cooking.prefer_faster")
    assert entry.outcome.value is False
    assert entry.priority_winner == "profile"


def test_profile_null_empty_memory_defaults_false():
    profile = {"cooktime": "medium", "cooking_preferences": {"prefer_faster_meals": None}}
    applied = _apply(profile)
    assert applied.prefer_faster_meals is False
    assert applied.cooking_time_limit == 45

    result = DecisionEngine().evaluate(profile)
    assert result.strategy.prefer_faster_meals is False
    assert result.decision.cooking.preference_source == "default"
    entry = _entry(result, "cooking.prefer_faster")
    assert entry.priority_winner == "default"
    assert entry.confidence == "fallback"


def test_profile_null_learned_active_applies_without_limit_change():
    profile = {"cooktime": "slow"}
    learned = _learned_faster()
    applied = _apply(profile, learned_faster=True)
    assert applied.prefer_faster_meals is True
    assert applied.cooking_time_limit == 90

    result = DecisionEngine().evaluate(profile, learned_context=learned)
    assert result.strategy.prefer_faster_meals is True
    assert result.strategy.cooking_time_limit == 90
    assert result.decision.cooking.preference_source == "learned_preference"
    entry = _entry(result, "cooking.prefer_faster")
    assert entry.priority_winner == "learned_preference"


def test_profile_false_vetoes_learned_and_memory():
    profile = {
        "cooktime": "medium",
        "cooking_preferences": {"prefer_faster_meals": False},
    }
    result = DecisionEngine().evaluate(
        profile,
        _memory_faster(),
        learned_context=_learned_faster(),
    )
    assert result.strategy.prefer_faster_meals is False
    assert result.strategy.cooking_time_limit == 45
    assert result.decision.cooking.preference_source == "profile"
    entry = _entry(result, "cooking.prefer_faster")
    assert entry.priority_winner == "profile"
    skipped_codes = {rule.rule_code for rule in entry.rejected_rules if rule.result == "skipped"}
    assert "LEARNED_FASTER_PREFERENCE" in skipped_codes
    assert "MEMORY_FASTER_PREFERENCE" in skipped_codes


def test_flag_off_explicit_profile_true_survives_empty_memory():
    profile = {
        "cooktime": "medium",
        "cooking_preferences": {"prefer_faster_meals": True},
    }
    disabled = LearnedPreferencesContext.empty(enabled=False)
    result = DecisionEngine().evaluate(profile, learned_context=disabled)
    assert result.strategy.prefer_faster_meals is True
    assert result.decision.cooking.preference_source == "profile"
    assert result.build_result.applied_learned_preferences is not None
    assert result.build_result.applied_learned_preferences.enabled is False
    assert result.build_result.applied_learned_preferences.decisions == []


def test_legacy_profile_without_cooking_preferences_defaults():
    profile = {"cooktime": "fast", "goal": "home"}
    assert "cooking_preferences" not in profile
    applied = _apply(profile)
    assert applied.prefer_faster_meals is False
    assert applied.cooking_time_limit == 20

    result = DecisionEngine().evaluate(profile)
    assert result.strategy.prefer_faster_meals is False
    assert result.strategy.cooking_time_limit == 20
    assert result.decision.cooking.preference_source == "default"


# --- Parity / independence guards ---


def test_unrelated_avoid_signal_does_not_change_profile_faster():
    """Profile true must resolve identically with or without non-faster Memory."""
    profile = {
        "cooktime": "medium",
        "cooking_preferences": {"prefer_faster_meals": True},
    }
    avoid_only = StrategyMemoryContext(
        avoided_ingredients=("кинза",),
        signals=(
            ConfirmedMemorySignal(
                signal_id="avoid-1",
                signal_type=SignalType.AVOID_INGREDIENT.value,
                target_value="кинза",
                target_label="Кинза",
                confirmation_source="user",
            ),
        ),
    )
    empty = DecisionEngine().evaluate(profile)
    with_avoid = DecisionEngine().evaluate(profile, avoid_only)
    assert empty.strategy.prefer_faster_meals is True
    assert with_avoid.strategy.prefer_faster_meals is True
    assert empty.strategy.cooking_time_limit == with_avoid.strategy.cooking_time_limit
    assert empty.decision.cooking.preference_source == "profile"
    assert with_avoid.decision.cooking.preference_source == "profile"


def test_explanation_matches_profile_true_empty_memory():
    result = DecisionEngine().evaluate(
        {"cooking_preferences": {"prefer_faster_meals": True}, "cooktime": "medium"}
    )
    explanations = build_decision_explanations(
        result.trace, strategy=result.strategy, max_explanations=20
    )
    faster = next(
        item
        for item in explanations.explanations
        if item.decision_key == "cooking.prefer_faster"
    )
    assert faster.outcome == "Включено"
    assert "ИИ" not in faster.explanation


def test_time_limit_entry_independent_of_profile_faster():
    result = DecisionEngine().evaluate(
        {
            "cooktime": "slow",
            "cooking_preferences": {"prefer_faster_meals": True},
        }
    )
    limit_entry = _entry(result, "cooking.time_limit")
    faster_entry = _entry(result, "cooking.prefer_faster")
    assert limit_entry.outcome.value == 90
    assert faster_entry.outcome.value is True
