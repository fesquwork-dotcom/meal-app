"""Decision explanation helpers."""

from decision.engine import DecisionEngine
from decision.explanation import collect_decision_reasons, summarize_decision_sources


def test_collect_decision_reasons_includes_reason_codes():
    decision = DecisionEngine().resolve({"goal": "budget", "days": 7, "cooktime": "medium"})
    reasons = collect_decision_reasons(decision)

    codes = {reason.code for reason in reasons}
    assert "GOAL_BUDGET" in codes or any(code.startswith("GOAL_") for code in codes)
    assert reasons == sorted(reasons, key=lambda item: (item.priority, item.code))


def test_summarize_decision_sources_counts():
    decision = DecisionEngine().resolve({"goal": "home", "days": 5})
    summary = summarize_decision_sources(decision)
    assert isinstance(summary, dict)
    assert sum(summary.values()) >= 1
