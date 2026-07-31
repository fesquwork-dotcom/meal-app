"""DecisionTrace model contract: safety, versioning, immutability, round-trip."""

import pytest
from pydantic import ValidationError

from decision.trace_models import (
    DECISION_TRACE_VERSION,
    DecisionRuleTrace,
    DecisionSourceReference,
    DecisionTrace,
    DecisionTraceEntry,
    DecisionTraceValue,
    build_trace_summary,
)


def _entry(key: str = "cooking.cook_days") -> DecisionTraceEntry:
    return DecisionTraceEntry(
        decision_key=key,
        outcome=DecisionTraceValue.from_value([1, 3, 5]),
        sources=[
            DecisionSourceReference(source="rule", field=None, precedence=4, applied=True)
        ],
        applied_rules=[
            DecisionRuleTrace(
                rule_code="COOK_DAYS_BATCH_GOAL",
                result="applied",
                reason_code="COOK_DAYS_REDUCE_DAILY_WORK",
                input_summary={"goal": "budget", "days": 5},
            )
        ],
        rejected_rules=[
            DecisionRuleTrace(
                rule_code="COOK_DAYS_DAILY_FAST",
                result="rejected",
                reason_code="PROFILE_COOKTIME_NOT_FAST",
                input_summary={"cooktime": "medium"},
            )
        ],
        priority_winner="rule",
        confidence="deterministic",
    )


def test_trace_json_round_trip():
    trace = DecisionTrace(decision_version=1, entries=[_entry()])
    restored = DecisionTrace.from_json(trace.to_json())

    assert restored is not None
    assert restored.trace_version == DECISION_TRACE_VERSION
    assert restored.entries[0].decision_key == "cooking.cook_days"
    assert restored.entries[0].outcome.value == [1, 3, 5]
    assert restored.entries[0].applied_rules[0].rule_code == "COOK_DAYS_BATCH_GOAL"
    assert restored == trace


def test_trace_stable_ordering_preserved():
    trace = DecisionTrace(
        decision_version=1,
        entries=[_entry("budget.weekly"), _entry("cooking.cook_days")],
    )
    restored = DecisionTrace.from_json(trace.to_json())
    assert [e.decision_key for e in restored.entries] == [
        "budget.weekly",
        "cooking.cook_days",
    ]


def test_trace_value_rejects_arbitrary_objects():
    with pytest.raises(ValidationError):
        DecisionTraceValue(display_type="list", value=[{"nested": "dict"}])
    with pytest.raises(ValueError):
        DecisionTraceValue.from_value(object())


def test_input_summary_rejects_non_allowlisted_keys():
    with pytest.raises(ValidationError):
        DecisionRuleTrace(
            rule_code="X",
            result="applied",
            reason_code="Y",
            input_summary={"allergies": "орехи"},
        )


def test_input_summary_rejects_non_scalar_values():
    with pytest.raises(ValidationError):
        DecisionRuleTrace(
            rule_code="X",
            result="applied",
            reason_code="Y",
            input_summary={"goal": ["budget"]},
        )


def test_trace_models_are_frozen():
    trace = DecisionTrace(decision_version=1, entries=[_entry()])
    with pytest.raises(ValidationError):
        trace.trace_version = 2
    with pytest.raises(ValidationError):
        trace.entries[0].priority_winner = "profile"


def test_from_json_rejects_unsupported_version():
    trace = DecisionTrace(decision_version=1, entries=[])
    payload = trace.to_json().replace('"trace_version":1', '"trace_version":99')
    assert DecisionTrace.from_json(payload) is None


def test_from_json_handles_malformed_payloads():
    assert DecisionTrace.from_json(None) is None
    assert DecisionTrace.from_json("") is None
    assert DecisionTrace.from_json("{broken") is None
    assert DecisionTrace.from_json("[1,2]") is None


def test_build_trace_summary_counts():
    trace = DecisionTrace(decision_version=1, entries=[_entry(), _entry("shopping.days")])
    summary = build_trace_summary(trace)

    assert summary.trace_version == DECISION_TRACE_VERSION
    assert summary.decision_count == 2
    assert summary.applied_rule_count == 2
    assert summary.rejected_rule_count == 2
    assert summary.fallback_decision_count == 0
    assert summary.source_counts == {"rule": 2}
