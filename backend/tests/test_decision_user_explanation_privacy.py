"""Public explanations never expose trace internals or sensitive targets."""

from decision.engine import DecisionEngine
from decision.user_explanation import build_decision_explanations
from trace_fixtures import behavior_availability, memory_avoid


def test_serialized_explanations_are_privacy_safe():
    result = DecisionEngine().evaluate(
        {
            "goal": "budget",
            "allergies": "орехи",
            "dietary_constraints": {"intolerances": ["молоко"]},
        },
        memory_avoid("гречка"),
        behavior_availability("киноа"),
    )
    raw = build_decision_explanations(
        result.trace, strategy=result.strategy
    ).model_dump_json()

    for forbidden in (
        "орехи",
        "молоко",
        "гречка",
        "киноа",
        "sig-avoid-1",
        "insight-availability-1",
        "rule_code",
        "reason_code",
        "precedence",
        "input_summary",
        "COOK_DAYS_",
        "MEMORY_",
        "BEHAVIOR_",
    ):
        assert forbidden not in raw


def test_exclusion_explanation_is_neutral_without_count():
    result = DecisionEngine().evaluate(
        {"allergies": "орехи"}, memory_avoid("гречка")
    )
    collection = build_decision_explanations(result.trace, strategy=result.strategy)
    item = next(
        explanation
        for explanation in collection.explanations
        if explanation.decision_key in {"protein.excluded", "exclusions.count"}
    )
    assert item.outcome == "Учтены"
    assert not any(character.isdigit() for character in item.explanation)
    assert item.source_label is None


def test_public_model_has_no_technical_fields():
    result = DecisionEngine().evaluate({"goal": "home"})
    item = build_decision_explanations(
        result.trace, strategy=result.strategy
    ).explanations[0]
    assert set(item.model_dump()) == {
        "version",
        "decision_key",
        "title",
        "outcome",
        "explanation",
        "source_label",
        "supporting_points",
        "alternative_note",
        "confidence_label",
    }
