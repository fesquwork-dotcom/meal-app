"""Pass / warn / fail thresholds for stress-test reports."""

from __future__ import annotations

from typing import Any, Literal

Verdict = Literal["PASS", "WARN", "FAIL"]


def evaluate_thresholds(aggregate: dict[str, Any]) -> dict[str, Any]:
    """Evaluate aggregate metrics against Sprint 10.4 initial thresholds."""
    total = int(aggregate.get("total_runs") or 0)
    if total == 0:
        return {
            "verdict": "FAIL",
            "reasons": ["no runs completed"],
            "checks": {},
        }

    success_rate = float(aggregate.get("success_rate") or 0.0)
    unexpected = int(aggregate.get("unexpected_failure_count") or 0)
    success_by_2 = float(aggregate.get("success_by_attempt_2_rate") or 0.0)
    max_tokens = float(aggregate.get("max_tokens_failure_rate") or 0.0)
    parse_schema = float(aggregate.get("parse_schema_failure_rate") or 0.0)
    regression = float(aggregate.get("correction_regression_rate") or 0.0)
    controlled = float(aggregate.get("controlled_failure_rate") or 0.0)

    checks = {
        "success_rate": success_rate,
        "unexpected_failure_count": unexpected,
        "success_by_attempt_2_rate": success_by_2,
        "max_tokens_failure_rate": max_tokens,
        "parse_schema_failure_rate": parse_schema,
        "correction_regression_rate": regression,
        "controlled_failure_rate": controlled,
    }

    fail_reasons: list[str] = []
    warn_reasons: list[str] = []

    if unexpected > 0:
        fail_reasons.append(f"unexpected_failure_count={unexpected} > 0")
    if success_rate < 90.0:
        fail_reasons.append(f"success_rate={success_rate}% < 90%")
    if parse_schema > 3.0:
        fail_reasons.append(f"parse_schema_failure_rate={parse_schema}% > 3%")
    if max_tokens > 3.0:
        fail_reasons.append(f"max_tokens_failure_rate={max_tokens}% > 3%")

    if not fail_reasons:
        if success_rate < 95.0:
            warn_reasons.append(f"success_rate={success_rate}% < 95%")
        if success_by_2 < 90.0:
            warn_reasons.append(f"success_by_attempt_2_rate={success_by_2}% < 90%")
        if max_tokens > 1.0:
            warn_reasons.append(f"max_tokens_failure_rate={max_tokens}% > 1%")
        if parse_schema > 1.0:
            warn_reasons.append(f"parse_schema_failure_rate={parse_schema}% > 1%")
        if regression > 20.0:
            # Above WARN band for regression → still WARN (not FAIL unless other FAIL rules).
            warn_reasons.append(f"correction_regression_rate={regression}% > 20%")
        elif regression > 10.0:
            warn_reasons.append(f"correction_regression_rate={regression}% > 10%")
        if controlled > 10.0:
            warn_reasons.append(f"controlled_failure_rate={controlled}% > 10%")
        elif controlled > 5.0:
            warn_reasons.append(f"controlled_failure_rate={controlled}% > 5%")

    if fail_reasons:
        verdict: Verdict = "FAIL"
    elif warn_reasons:
        verdict = "WARN"
    else:
        verdict = "PASS"

    return {
        "verdict": verdict,
        "reasons": fail_reasons or warn_reasons or ["all threshold checks passed"],
        "checks": checks,
        "fail_reasons": fail_reasons,
        "warn_reasons": warn_reasons,
    }
