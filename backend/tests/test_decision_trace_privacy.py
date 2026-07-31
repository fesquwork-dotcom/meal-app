"""Trace privacy: no sensitive targets, IDs, or free text leak into JSON."""

from decision.engine import DecisionEngine
from trace_fixtures import behavior_availability, memory_avoid, memory_faster

FORBIDDEN_VALUES = [
    "орехи",          # allergy value
    "гречка",         # memory avoid target
    "киноа",          # behavior availability target
    "sig-avoid-1",    # signal ID
    "sig-faster-1",   # signal ID
    "insight-availability-1",  # insight ID
    "молоко",         # dietary constraint value
]


def _trace_json_for_sensitive_profile() -> str:
    profile = {
        "goal": "budget",
        "days": 7,
        "cooktime": "medium",
        "allergies": "орехи",
        "dietary_constraints": {"allergies": ["орехи"], "intolerances": ["молоко"]},
    }
    result = DecisionEngine().evaluate(
        profile, memory_avoid("гречка"), behavior_availability("киноа")
    )
    return result.trace.to_json()


def test_trace_contains_no_sensitive_values():
    raw = _trace_json_for_sensitive_profile()
    for value in FORBIDDEN_VALUES:
        assert value not in raw, f"sensitive value leaked into trace: {value}"


def test_trace_does_not_leak_user_id():
    raw = _trace_json_for_sensitive_profile()
    assert "user_id" not in raw
    assert "telegram" not in raw.lower()


def test_availability_outcome_is_count_not_values():
    result = DecisionEngine().evaluate({}, None, behavior_availability("киноа"))
    entry = next(
        e for e in result.trace.entries
        if e.decision_key == "behavior.availability_avoid_products"
    )
    assert entry.outcome.display_type == "number"
    assert entry.outcome.value == 1


def test_exclusions_outcome_is_count_not_values():
    result = DecisionEngine().evaluate({"allergies": "орехи"}, memory_avoid("гречка"))
    entry = next(e for e in result.trace.entries if e.decision_key == "exclusions.count")
    assert entry.outcome.display_type == "number"
    # Both allergy and memory avoid excluded, but only the count is traced.
    assert entry.outcome.value == 2


def test_decision_context_still_holds_actual_exclusions():
    result = DecisionEngine().evaluate({"allergies": "орехи"}, memory_avoid("гречка"))
    excluded_lower = [item.lower() for item in result.decision.excluded_products]
    assert any("орех" in item for item in excluded_lower)
    assert any("греч" in item for item in excluded_lower)


def test_trace_has_no_evidence_or_prompt_fields():
    raw = _trace_json_for_sensitive_profile()
    for forbidden_key in ("evidence", "prompt", "target_value", "target_label", "target_key"):
        assert forbidden_key not in raw
