"""Pure deterministic Decision Outcome evaluation."""

from decision.engine import DecisionEngine
from decision.outcome import evaluate_decision_outcomes
from memory.records import MemoryEventRecord


def _event(index: int, *, reason: str = "generic") -> MemoryEventRecord:
    return MemoryEventRecord(
        id=f"private-event-{index}",
        user_id=1,
        event_type="meal_replaced",
        event_key=f"request-{index}",
        strategy_id="strategy-private",
        meal_id=f"meal-private-{index}",
        recipe_id=f"recipe-private-{index}",
        reason_code=reason,
        target_type="ingredient",
        target_value="private-ingredient",
        target_label="Private ingredient",
        metadata_json=None,
        created_at=f"2026-07-{index + 1:02d}T10:00:00+00:00",
    )


def _outcome(collection, key):
    return next(item for item in collection.outcomes if item.decision_key == key)


def test_low_replacement_rate_is_successful():
    result = DecisionEngine().evaluate({"days": 7, "goal": "home"})
    collection = evaluate_decision_outcomes(
        result.trace, [_event(0)], strategy=result.strategy
    )
    assert _outcome(collection, "planning.prefer_familiar_meals").status == "successful"
    assert _outcome(collection, "cooking.cook_days").status == "successful"


def test_high_replacement_rate_is_unsuccessful():
    result = DecisionEngine().evaluate({"days": 7, "goal": "home"})
    events = [_event(index) for index in range(9)]
    collection = evaluate_decision_outcomes(
        result.trace, events, strategy=result.strategy
    )
    outcome = _outcome(collection, "planning.prefer_familiar_meals")
    assert outcome.status == "unsuccessful"
    assert outcome.result == "high_replacement_rate"
    assert outcome.confidence == "strong"


def test_no_events_is_insufficient_not_false_success():
    result = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        result.trace, [], strategy=result.strategy
    )
    supported = [
        item
        for item in collection.outcomes
        if item.decision_key
        in {
            "planning.prefer_familiar_meals",
            "cooking.prefer_faster",
            "behavior.availability_avoid_products",
            "cooking.cook_days",
            "shopping.days",
        }
    ]
    assert supported
    assert {item.status for item in supported} == {"insufficient_data"}


def test_unsupported_decisions_remain_pending():
    result = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        result.trace, [_event(0)], strategy=result.strategy
    )
    budget = _outcome(collection, "budget.weekly")
    assert budget.status == "pending"
    assert budget.result == "evaluation_not_supported"


def test_faster_replacement_reason_marks_faster_decision_unsuccessful():
    result = DecisionEngine().evaluate(
        {"days": 7, "cooking_preferences": {"prefer_faster_meals": True}},
    )
    collection = evaluate_decision_outcomes(
        result.trace,
        [_event(0, reason="faster"), _event(1, reason="faster")],
        strategy=result.strategy,
    )
    faster = _outcome(collection, "cooking.prefer_faster")
    assert faster.status == "unsuccessful"
    assert faster.result == "faster_replacements_persisted"


def test_availability_and_shopping_use_unavailable_reason_only():
    result = DecisionEngine().evaluate({"days": 7})
    successful = evaluate_decision_outcomes(
        result.trace, [_event(0)], strategy=result.strategy
    )
    assert (
        _outcome(successful, "behavior.availability_avoid_products").status
        == "successful"
    )
    assert _outcome(successful, "shopping.days").status == "successful"

    friction = evaluate_decision_outcomes(
        result.trace,
        [_event(index, reason="ingredient_unavailable") for index in range(3)],
        strategy=result.strategy,
    )
    assert (
        _outcome(friction, "behavior.availability_avoid_products").status
        == "unsuccessful"
    )
    assert _outcome(friction, "shopping.days").status == "unsuccessful"


def test_evaluation_is_deterministic_and_event_order_independent():
    result = DecisionEngine().evaluate({"days": 7})
    events = [_event(0), _event(1, reason="ingredient_unavailable")]
    first = evaluate_decision_outcomes(
        result.trace, events, strategy=result.strategy
    )
    second = evaluate_decision_outcomes(
        result.trace, list(reversed(events)), strategy=result.strategy
    )
    assert first == second
