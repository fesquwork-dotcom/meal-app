"""Outcome persistence and API projections contain aggregates only."""

from decision.engine import DecisionEngine
from decision.outcome import build_outcome_summary, evaluate_decision_outcomes
from test_decision_outcomes import _event


SENSITIVE_VALUES = (
    "private-event",
    "request-",
    "strategy-private",
    "meal-private",
    "recipe-private",
    "private-ingredient",
    "Private ingredient",
)


def test_outcome_collection_does_not_copy_event_identifiers_or_targets():
    evaluation = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        evaluation.trace,
        [_event(0, reason="ingredient_unavailable")],
        strategy=evaluation.strategy,
    )
    raw = collection.to_json()
    for sensitive in SENSITIVE_VALUES:
        assert sensitive not in raw


def test_public_summary_hides_internal_result_and_evidence():
    evaluation = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        evaluation.trace,
        [_event(0, reason="ingredient_unavailable")],
        strategy=evaluation.strategy,
    )
    raw = build_outcome_summary(collection).model_dump_json()
    for internal in (
        "evidence_count",
        "result",
        "confidence",
        "feedback",
        "recommendation",
        "ingredient_unavailable",
    ):
        assert internal not in raw


def test_outcome_explanations_use_allowlisted_decision_keys_only():
    evaluation = DecisionEngine().evaluate({"days": 7})
    summary = build_outcome_summary(
        evaluate_decision_outcomes(
            evaluation.trace, [_event(0)], strategy=evaluation.strategy
        )
    )
    assert {
        item.decision_key for item in summary.explanations
    } <= {
        "planning.prefer_familiar_meals",
        "cooking.prefer_faster",
        "behavior.availability_avoid_products",
        "cooking.cook_days",
        "shopping.days",
    }
