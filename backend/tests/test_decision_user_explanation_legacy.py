"""Legacy fallback never invents trace provenance."""

from decision.engine import DecisionEngine
from decision.user_explanation import build_legacy_decision_explanations
from strategy.explanation import build_strategy_explanation


def test_legacy_collection_uses_existing_strategy_explanation():
    result = DecisionEngine().evaluate({"goal": "budget", "days": 5})
    strategy_explanation = build_strategy_explanation(result.strategy)
    collection = build_legacy_decision_explanations(strategy_explanation)

    assert collection.source == "legacy"
    assert collection.headline == strategy_explanation.headline
    assert len(collection.explanations) <= 8
    assert collection.explanations


def test_legacy_items_have_no_priority_or_alternative_claims():
    result = DecisionEngine().evaluate({"goal": "home", "days": 5})
    collection = build_legacy_decision_explanations(
        build_strategy_explanation(result.strategy)
    )
    for item in collection.explanations:
        assert item.source_label is None
        assert item.confidence_label is None
        assert item.alternative_note is None
        assert item.decision_key.startswith("legacy.")


def test_legacy_output_is_limited():
    result = DecisionEngine().evaluate({"goal": "budget", "days": 7})
    collection = build_legacy_decision_explanations(
        build_strategy_explanation(result.strategy)
    )
    assert len(collection.explanations) <= 8
