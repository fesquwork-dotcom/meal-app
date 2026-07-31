"""Consistency between explanation reason codes and trace provenance."""

from decision.engine import DecisionEngine
from decision.trace_builder import find_trace_consistency_issues
from trace_fixtures import behavior_availability, memory_avoid, memory_faster

CONSISTENCY_MATRIX = [
    ({"goal": "home", "days": 7, "cooktime": "medium"}, None, None),
    ({"goal": "budget", "days": 7, "cooktime": "medium", "budget": 3000.0}, None, None),
    ({"goal": "healthy", "days": 5, "cooktime": "fast"}, None, None),
    ({"goal": "weight_loss", "days": 5}, None, None),
    ({"goal": "muscle", "days": 7, "proteins": ["chicken", "fish"]}, None, None),
    (
        {"cooking_preferences": {"prefer_faster_meals": False}, "cooktime": "medium"},
        "faster",
        None,
    ),
    ({"cooktime": ""}, "faster", None),
    ({"allergies": "гречка"}, "avoid", None),
    ({"goal": "home", "days": 5}, None, "availability"),
    ({"planning_preferences": {"prefer_familiar_meals": True}}, None, None),
    ({}, None, None),
]


def _contexts(memory_kind, behavior_kind):
    memory = None
    if memory_kind == "faster":
        memory = memory_faster()
    elif memory_kind == "avoid":
        memory = memory_avoid("гречка")
    behavior = behavior_availability("киноа") if behavior_kind == "availability" else None
    return memory, behavior


def test_reason_codes_have_matching_trace_rules_across_matrix():
    for profile, memory_kind, behavior_kind in CONSISTENCY_MATRIX:
        memory, behavior = _contexts(memory_kind, behavior_kind)
        result = DecisionEngine().evaluate(profile, memory, behavior)

        issues = find_trace_consistency_issues(result.trace, result.reason_codes)
        assert issues == [], f"profile={profile} issues={issues}"


def test_no_duplicate_decision_keys():
    result = DecisionEngine().evaluate({"goal": "budget", "days": 7})
    keys = [entry.decision_key for entry in result.trace.entries]
    assert len(keys) == len(set(keys))


def test_every_winner_present_in_entry_sources():
    result = DecisionEngine().evaluate(
        {"goal": "budget", "days": 7, "cooktime": "medium"},
        memory_faster(),
        behavior_availability("киноа"),
    )
    for entry in result.trace.entries:
        assert entry.priority_winner is not None
        assert entry.priority_winner in {source.source for source in entry.sources}


def test_duplicate_keys_detected_by_validator():
    result = DecisionEngine().evaluate({"goal": "home", "days": 5})
    trace = result.trace
    duplicated = trace.model_copy(update={"entries": trace.entries + [trace.entries[0]]})
    issues = find_trace_consistency_issues(duplicated, result.reason_codes)
    assert any(issue.startswith("duplicate_decision_key:") for issue in issues)


def test_unknown_reason_code_reported():
    result = DecisionEngine().evaluate({"goal": "home", "days": 5})
    issues = find_trace_consistency_issues(
        result.trace, list(result.reason_codes) + ["TOTALLY_UNKNOWN_CODE"]
    )
    assert "reason_code_without_trace_rule:TOTALLY_UNKNOWN_CODE" in issues


def test_trace_may_contain_more_rules_than_explanation():
    result = DecisionEngine().evaluate({"goal": "restaurant", "days": 5})
    trace_rule_count = sum(
        len(entry.applied_rules) + len(entry.rejected_rules)
        for entry in result.trace.entries
    )
    assert trace_rule_count >= len(result.reason_codes) - 5
    assert find_trace_consistency_issues(result.trace, result.reason_codes) == []
