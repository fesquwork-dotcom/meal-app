"""Priority provenance: who wins and what gets skipped."""

from decision.engine import DecisionEngine
from trace_fixtures import behavior_availability, memory_avoid, memory_faster


def _entry(trace, key):
    return next(entry for entry in trace.entries if entry.decision_key == key)


def test_profile_explicit_false_wins_over_memory_true():
    result = DecisionEngine().evaluate(
        {"cooking_preferences": {"prefer_faster_meals": False}, "cooktime": "medium"},
        memory_faster(),
    )
    entry = _entry(result.trace, "cooking.prefer_faster")

    assert entry.outcome.value is False
    assert entry.priority_winner == "profile"
    assert entry.confidence == "explicit"

    profile_source = next(s for s in entry.sources if s.source == "profile")
    memory_source = next(s for s in entry.sources if s.source == "memory")
    assert profile_source.applied is True
    assert memory_source.applied is False

    skipped = [r for r in entry.rejected_rules if r.result == "skipped"]
    assert skipped and skipped[0].rule_code == "MEMORY_FASTER_PREFERENCE"
    assert skipped[0].reason_code == "MEMORY_SIGNAL_IGNORED_PROFILE_PRIORITY"


def test_profile_true_marks_memory_redundant():
    result = DecisionEngine().evaluate(
        {"cooking_preferences": {"prefer_faster_meals": True}, "cooktime": "medium"},
        memory_faster(),
    )
    entry = _entry(result.trace, "cooking.prefer_faster")

    assert entry.outcome.value is True
    assert entry.priority_winner == "profile"
    skipped = [r for r in entry.rejected_rules if r.result == "skipped"]
    assert skipped and skipped[0].reason_code == "MEMORY_FASTER_MEALS_REDUNDANT_WITH_PROFILE"


def test_memory_wins_when_profile_unset():
    result = DecisionEngine().evaluate({"cooktime": "medium"}, memory_faster())
    entry = _entry(result.trace, "cooking.prefer_faster")

    assert entry.outcome.value is True
    assert entry.priority_winner == "memory"
    assert entry.confidence == "inferred"
    memory_source = next(s for s in entry.sources if s.source == "memory")
    assert memory_source.applied is True


def test_default_fallback_when_no_sources():
    result = DecisionEngine().evaluate({"cooktime": "medium"})
    entry = _entry(result.trace, "cooking.prefer_faster")

    assert entry.outcome.value is False
    assert entry.priority_winner == "default"
    assert entry.confidence == "fallback"


def test_behavior_wins_over_default_for_availability():
    with_behavior = DecisionEngine().evaluate({}, None, behavior_availability("киноа"))
    without_behavior = DecisionEngine().evaluate({})

    applied = _entry(with_behavior.trace, "behavior.availability_avoid_products")
    fallback = _entry(without_behavior.trace, "behavior.availability_avoid_products")
    assert applied.priority_winner == "behavior"
    assert fallback.priority_winner == "default"
    assert fallback.confidence == "fallback"


def test_memory_redundant_with_profile_exclusion_traced():
    result = DecisionEngine().evaluate({"allergies": "гречка"}, memory_avoid("гречка"))
    entry = _entry(result.trace, "exclusions.count")

    rejected_reasons = [rule.reason_code for rule in entry.rejected_rules]
    assert "MEMORY_SIGNAL_REDUNDANT_WITH_PROFILE_CONSTRAINT" in rejected_reasons
    assert entry.priority_winner == "profile"


def test_every_winner_exists_in_sources():
    result = DecisionEngine().evaluate(
        {"goal": "budget", "days": 7, "cooktime": "medium"},
        memory_faster(),
        behavior_availability("киноа"),
    )
    for entry in result.trace.entries:
        source_names = {source.source for source in entry.sources}
        assert entry.priority_winner in source_names
