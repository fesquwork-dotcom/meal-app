"""Sprint 9.3 — pure Learned Preference effectiveness evaluator."""

from __future__ import annotations

from datetime import date, timedelta

from learned_preferences.effectiveness import (
    evaluate_learned_preference_effectiveness,
)
from learned_preferences.effectiveness_models import (
    LearnedPreferencePlanObservation,
)
from learned_preferences.effectiveness_presentation import present_effectiveness


def _obs(
    day: int,
    *,
    applied: bool = True,
    replacements: int | None = 0,
    planned: int | None = 10,
    suited: int = 0,
    cooked: int = 0,
    completed: bool = False,
    outcome: str | None = None,
) -> LearnedPreferencePlanObservation:
    return LearnedPreferencePlanObservation(
        plan_date=date(2026, 1, 1) + timedelta(days=day * 7),
        preference_applied=applied,
        replacement_count=replacements,
        planned_meal_count=planned,
        meal_suited_count=suited,
        meal_cooked_count=cooked,
        plan_completed=completed,
        decision_outcome=outcome,
    )


def test_no_plans_is_insufficient():
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals", []
    )
    assert result.status == "insufficient_data"
    assert result.confidence == "insufficient"
    assert result.summary_code == "INSUFFICIENT_DATA"


def test_one_plan_is_insufficient_even_when_positive():
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals",
        [_obs(0, outcome="successful", suited=3)],
    )
    assert result.status == "insufficient_data"
    assert result.applied_plans == 1


def test_partial_positive_is_emerging_not_effective():
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals",
        [
            _obs(0, outcome="successful", suited=2),
            _obs(1, outcome="successful", suited=2),
            _obs(2, completed=True),
        ],
    )
    assert result.confidence == "partial"
    assert result.status == "emerging"
    assert result.summary_code == "EMERGING_POSITIVE"


def test_established_effective():
    plans = [
        _obs(i, outcome="successful", suited=3)
        for i in range(4)
    ]
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals", plans
    )
    assert result.confidence == "established"
    assert result.status == "effective"
    assert result.positive_evidence_count == 4


def test_established_ineffective_high_replacements():
    plans = [
        _obs(i, replacements=5, planned=10, outcome="unsuccessful")
        for i in range(4)
    ]
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals", plans
    )
    assert result.status == "ineffective"
    assert result.negative_evidence_count == 4


def test_mixed_is_neutral():
    plans = [
        _obs(0, outcome="successful", suited=3),
        _obs(1, outcome="successful", suited=3),
        _obs(2, replacements=5, planned=10, outcome="unsuccessful"),
        _obs(3, replacements=5, planned=10, outcome="unsuccessful"),
    ]
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals", plans
    )
    assert result.status == "neutral"
    assert "MIXED_EVIDENCE" in result.limitations


def test_positive_does_not_mask_high_replacements():
    # plan_completed + suited would look positive, but high replacement wins.
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals",
        [
            _obs(
                i,
                replacements=5,
                planned=10,
                suited=3,
                completed=True,
                outcome="successful",
            )
            for i in range(4)
        ],
    )
    assert result.status == "ineffective"
    assert result.positive_evidence_count == 0
    assert result.negative_evidence_count == 4


def test_absent_positive_is_not_negative():
    plans = [_obs(i, replacements=0, planned=10) for i in range(4)]
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals", plans
    )
    assert result.negative_evidence_count == 0
    assert result.positive_evidence_count == 0
    assert result.status == "neutral"
    assert "ABSENT_POSITIVE_NOT_NEGATIVE" in result.limitations


def test_non_applied_plans_excluded():
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals",
        [
            _obs(0, applied=False, outcome="successful", suited=3),
            _obs(1, applied=False, replacements=5, planned=10),
        ],
    )
    assert result.applied_plans == 0
    assert result.status == "insufficient_data"


def test_unsupported_type_insufficient():
    result = evaluate_learned_preference_effectiveness(
        "stable_cook_days",
        [_obs(0, outcome="successful")],
    )
    assert result.status == "insufficient_data"
    assert result.summary_code == "UNSUPPORTED_TYPE"


def test_faster_positive_uses_cooked_and_suited():
    plans = [
        _obs(i, cooked=2, suited=2, replacements=0, planned=10)
        for i in range(4)
    ]
    result = evaluate_learned_preference_effectiveness(
        "prefer_fast_meals", plans
    )
    assert result.status == "effective"


def test_deterministic_and_order_independent():
    plans = [
        _obs(3, outcome="successful", suited=2),
        _obs(0, replacements=5, planned=10, outcome="unsuccessful"),
        _obs(2, outcome="successful", suited=2),
        _obs(1, replacements=5, planned=10, outcome="unsuccessful"),
    ]
    first = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals", plans
    )
    second = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals", list(reversed(plans))
    )
    assert first == second


def test_presentation_is_allowlisted_and_privacy_safe():
    result = evaluate_learned_preference_effectiveness(
        "prefer_familiar_meals",
        [_obs(i, outcome="successful", suited=3) for i in range(4)],
    )
    payload = present_effectiveness(result)
    text = payload.model_dump_json()
    assert "strategy" not in text.lower()
    assert "event_id" not in text
    assert "%" not in text
    assert "87" not in text
    assert payload.title
    assert payload.evidence_text.startswith("Основано")
