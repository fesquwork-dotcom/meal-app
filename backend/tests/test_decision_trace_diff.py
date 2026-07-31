"""compare_decision_traces: change detection without false positives."""

from decision.engine import DecisionEngine
from decision.trace_diff import compare_decision_traces
from decision.trace_models import DecisionTrace


def _trace(profile):
    return DecisionEngine().evaluate(profile).trace


def test_identical_traces_produce_no_diff():
    profile = {"goal": "budget", "days": 7, "cooktime": "medium"}
    diff = compare_decision_traces(_trace(profile), _trace(profile))

    assert diff.current_trace_available and diff.next_trace_available
    assert diff.has_changes is False
    assert diff.changed_keys == []


def test_value_change_detected():
    current = _trace({"goal": "budget", "days": 7, "budget": 3000.0})
    nxt = _trace({"goal": "budget", "days": 7, "budget": 4000.0})
    diff = compare_decision_traces(current, nxt)

    assert "budget.weekly" in diff.changed_keys
    change = next(c for c in diff.changes if c.decision_key == "budget.weekly")
    assert change.value_changed is True


def test_winner_and_rule_change_detected():
    current = _trace({"goal": "budget", "days": 7, "cooktime": "medium"})
    nxt = _trace({"goal": "restaurant", "days": 7, "cooktime": "medium"})
    diff = compare_decision_traces(current, nxt)

    cook_change = next(c for c in diff.changes if c.decision_key == "cooking.cook_days")
    assert cook_change.value_changed or cook_change.applied_rules_changed


def test_fallback_to_explicit_transition_detected():
    current = _trace({"days": 5})
    nxt = _trace({"days": 5, "budget": 3000.0})
    diff = compare_decision_traces(current, nxt)

    change = next(c for c in diff.changes if c.decision_key == "budget.weekly")
    assert change.confidence_changed is True


def test_entry_ordering_does_not_produce_false_diff():
    trace = _trace({"goal": "home", "days": 5})
    reordered = DecisionTrace(
        trace_version=trace.trace_version,
        decision_version=trace.decision_version,
        entries=list(reversed(trace.entries)),
    )
    diff = compare_decision_traces(trace, reordered)
    assert diff.has_changes is False


def test_missing_legacy_trace_reported_as_unavailable():
    trace = _trace({"goal": "home", "days": 5})

    diff = compare_decision_traces(None, trace)
    assert diff.current_trace_available is False
    assert diff.next_trace_available is True
    assert diff.has_changes is False

    diff_both_none = compare_decision_traces(None, None)
    assert diff_both_none.current_trace_available is False
    assert diff_both_none.next_trace_available is False
