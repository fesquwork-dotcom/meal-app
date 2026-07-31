"""Sprint 6.5 — positive events provide proof of success for outcomes."""

from decision.engine import DecisionEngine
from decision.outcome import build_outcome_summary, evaluate_decision_outcomes
from memory.records import MemoryEventRecord
from test_decision_outcomes import _event, _outcome


def _positive(
    index: int,
    event_type: str,
    *,
    meal_id: str | None = None,
) -> MemoryEventRecord:
    return MemoryEventRecord(
        id=f"positive-{index}",
        user_id=1,
        event_type=event_type,
        event_key=f"positive:strategy-private:{event_type}:{meal_id or ''}",
        strategy_id="strategy-private",
        meal_id=meal_id,
        recipe_id=None,
        reason_code=None,
        target_type=None,
        target_value=None,
        target_label=None,
        metadata_json=None,
        created_at=f"2026-07-{index + 1:02d}T12:00:00+00:00",
    )


def test_shopping_completed_confirms_shopping_and_availability():
    result = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        result.trace,
        [_positive(0, "shopping_completed")],
        strategy=result.strategy,
    )
    shopping = _outcome(collection, "shopping.days")
    assert shopping.status == "successful"
    assert shopping.result == "shopping_completed_confirmed"
    availability = _outcome(collection, "behavior.availability_avoid_products")
    assert availability.status == "successful"
    assert availability.result == "no_availability_friction_confirmed"


def test_cooked_meals_confirm_cook_days():
    result = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        result.trace,
        [
            _positive(0, "meal_cooked", meal_id="d1-breakfast"),
            _positive(1, "meal_cooked", meal_id="d2-dinner"),
        ],
        strategy=result.strategy,
    )
    cook_days = _outcome(collection, "cooking.cook_days")
    assert cook_days.status == "successful"
    assert cook_days.result == "meals_cooked_as_planned"
    assert cook_days.confidence == "moderate"
    assert cook_days.evidence_count == 2

    with_plan = evaluate_decision_outcomes(
        result.trace,
        [
            _positive(0, "meal_cooked", meal_id="d1-breakfast"),
            _positive(1, "meal_cooked", meal_id="d2-dinner"),
            _positive(2, "plan_completed"),
        ],
        strategy=result.strategy,
    )
    assert _outcome(with_plan, "cooking.cook_days").confidence == "strong"


def test_suited_meals_confirm_familiar_and_faster_decisions():
    result = DecisionEngine().evaluate(
        {"days": 7, "cooking_preferences": {"prefer_faster_meals": True}},
    )
    collection = evaluate_decision_outcomes(
        result.trace,
        [
            _positive(0, "meal_suited", meal_id="d1-breakfast"),
            _positive(1, "meal_suited", meal_id="d2-lunch"),
        ],
        strategy=result.strategy,
    )
    familiar = _outcome(collection, "planning.prefer_familiar_meals")
    assert familiar.status == "successful"
    assert familiar.result == "meals_suited_confirmed"
    faster = _outcome(collection, "cooking.prefer_faster")
    assert faster.status == "successful"


def test_single_mark_stays_below_evidence_threshold():
    result = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        result.trace,
        [_positive(0, "meal_suited", meal_id="d1-breakfast")],
        strategy=result.strategy,
    )
    assert (
        _outcome(collection, "planning.prefer_familiar_meals").status
        == "insufficient_data"
    )
    assert _outcome(collection, "cooking.cook_days").status == "insufficient_data"


def test_plan_completed_alone_confirms_plan_level_decisions_only():
    result = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        result.trace,
        [_positive(0, "plan_completed")],
        strategy=result.strategy,
    )
    assert _outcome(collection, "planning.prefer_familiar_meals").status == "successful"
    assert _outcome(collection, "cooking.cook_days").status == "successful"
    # Shopping decisions need a shopping mark; plan completion says nothing
    # about availability friction.
    assert _outcome(collection, "shopping.days").status == "insufficient_data"
    assert (
        _outcome(collection, "behavior.availability_avoid_products").status
        == "insufficient_data"
    )


def test_positive_marks_corroborate_replacement_based_success():
    result = DecisionEngine().evaluate({"days": 7})
    baseline = evaluate_decision_outcomes(
        result.trace, [_event(0)], strategy=result.strategy
    )
    assert _outcome(baseline, "planning.prefer_familiar_meals").confidence == "moderate"

    corroborated = evaluate_decision_outcomes(
        result.trace,
        [_event(0), _positive(1, "plan_completed")],
        strategy=result.strategy,
    )
    familiar = _outcome(corroborated, "planning.prefer_familiar_meals")
    assert familiar.status == "successful"
    assert familiar.confidence == "strong"


def test_positive_marks_do_not_hide_unsuccessful_outcomes():
    result = DecisionEngine().evaluate({"days": 7})
    events = [_event(index) for index in range(9)]
    events.append(_positive(10, "plan_completed"))
    collection = evaluate_decision_outcomes(
        result.trace, events, strategy=result.strategy
    )
    familiar = _outcome(collection, "planning.prefer_familiar_meals")
    assert familiar.status == "unsuccessful"
    assert familiar.result == "high_replacement_rate"


def test_summary_uses_confirmed_wording_for_positive_results():
    result = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        result.trace,
        [_positive(0, "shopping_completed"), _positive(1, "plan_completed")],
        strategy=result.strategy,
    )
    summary = build_outcome_summary(collection)
    shopping = next(
        item for item in summary.explanations if item.decision_key == "shopping.days"
    )
    assert shopping.status == "successful"
    assert "отметки подтвердили" in shopping.explanation.lower()
    # Aggregate texts never mention event internals.
    for item in summary.explanations:
        assert "shopping_completed" not in item.explanation
        assert "meal_" not in item.explanation


def test_evaluation_is_deterministic_with_positive_events():
    result = DecisionEngine().evaluate({"days": 7})
    events = [
        _event(0),
        _positive(1, "meal_cooked", meal_id="d1-breakfast"),
        _positive(2, "shopping_completed"),
    ]
    first = evaluate_decision_outcomes(result.trace, events, strategy=result.strategy)
    second = evaluate_decision_outcomes(
        result.trace, list(reversed(events)), strategy=result.strategy
    )
    assert first == second
