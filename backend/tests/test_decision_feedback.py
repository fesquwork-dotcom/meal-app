"""Feedback is stored as observation and never feeds DecisionEngine."""

from decision.engine import DecisionEngine
from decision.outcome import build_outcome_summary, evaluate_decision_outcomes
from test_decision_outcomes import _event


def test_feedback_generated_for_every_outcome():
    evaluation = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        evaluation.trace, [_event(0)], strategy=evaluation.strategy
    )
    assert len(collection.feedback) == len(collection.outcomes)
    assert {item.source for item in collection.feedback} == {"decision_outcome"}


def test_unsuccessful_feedback_does_not_recommend_automatic_change():
    evaluation = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        evaluation.trace,
        [_event(index) for index in range(9)],
        strategy=evaluation.strategy,
    )
    unsuccessful = [
        item
        for item in collection.feedback
        if "часто сопровождалось заменами" in item.feedback
    ]
    assert unsuccessful
    assert all("автомат" not in item.recommendation.lower() for item in unsuccessful)


def test_outcome_summary_is_safe_and_limited():
    evaluation = DecisionEngine().evaluate({"days": 7})
    collection = evaluate_decision_outcomes(
        evaluation.trace, [_event(0)], strategy=evaluation.strategy
    )
    summary = build_outcome_summary(collection)
    assert len(summary.explanations) <= 5
    assert summary.successful_count > 0
    assert "result" not in summary.model_dump_json()
    assert "evidence_count" not in summary.model_dump_json()


def test_outcomes_do_not_change_decision_engine_result():
    profile = {"goal": "budget", "days": 7, "cooktime": "medium"}
    before = DecisionEngine().evaluate(profile)
    evaluate_decision_outcomes(
        before.trace,
        [_event(index) for index in range(9)],
        strategy=before.strategy,
    )
    after = DecisionEngine().evaluate(profile)
    assert before.strategy.model_dump() == after.strategy.model_dump()
    assert before.trace == after.trace
