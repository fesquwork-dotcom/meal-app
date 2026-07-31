from decision.engine import DecisionEngine
from decision.learned_preferences_context import (
    ActiveLearnedPreference,
    LearnedPreferencesContext,
)
from decision.user_explanation import build_decision_explanations


def _context() -> LearnedPreferencesContext:
    return LearnedPreferencesContext(
        version=1,
        enabled=True,
        prefer_familiar_meals=True,
        prefer_faster_meals=True,
        source_preferences=(
            ActiveLearnedPreference("prefer_familiar_meals", 1),
            ActiveLearnedPreference("prefer_fast_meals", 1),
        ),
    )


def _entry(result, key):
    return next(
        item for item in result.trace.entries if item.decision_key == key
    )


def test_trace_records_learned_winner_without_ids_or_evidence():
    result = DecisionEngine().evaluate({}, learned_context=_context())
    entry = _entry(result, "cooking.prefer_faster")
    assert entry.priority_winner == "learned_preference"
    assert any(
        source.source == "learned_preference" and source.applied
        for source in entry.sources
    )
    raw = result.trace.model_dump_json().lower()
    for forbidden in ("preference_id", "recommendation_id", "evidence_json", "user_id"):
        assert forbidden not in raw


def test_profile_priority_records_learned_as_skipped():
    result = DecisionEngine().evaluate(
        {"cooking_preferences": {"prefer_faster_meals": False}},
        learned_context=_context(),
    )
    entry = _entry(result, "cooking.prefer_faster")
    assert entry.priority_winner == "profile"
    assert any(
        rule.rule_code == "LEARNED_FASTER_PREFERENCE"
        and rule.result == "skipped"
        and rule.reason_code
        == "LEARNED_PREFERENCE_IGNORED_PROFILE_PRIORITY"
        for rule in entry.rejected_rules
    )


def test_explanations_use_safe_learned_template():
    result = DecisionEngine().evaluate({}, learned_context=_context())
    explanations = build_decision_explanations(
        result.trace, strategy=result.strategy, max_explanations=20
    )
    text = explanations.model_dump_json()
    assert "которое вы ранее разрешили использовать" in text
    assert "ИИ решил" not in text
    assert "вероятност" not in text
