"""Decision-level explanation helpers (codes + sources), complementary to StrategyExplanation."""

from __future__ import annotations

from decision.context import DecisionContext
from decision.models import DecisionReason

REASON_SOURCE_PRIORITY: dict[str, int] = {
    "profile": 1,
    "memory": 2,
    "behavior": 3,
    "rule": 4,
    "default": 5,
    "runtime": 6,
}


def collect_decision_reasons(decision: DecisionContext) -> list[DecisionReason]:
    """Flattens nested DecisionReason entries with stable ordering."""
    reasons: list[DecisionReason] = []
    reasons.extend(decision.budget.reasons)
    reasons.extend(decision.cooking.reasons)
    reasons.extend(decision.protein.reasons)
    reasons.extend(decision.shopping.reasons)
    reasons.extend(decision.behavior.reasons)
    reasons.extend(decision.memory.reasons)

    # Also surface recorded reason codes that lack nested DecisionReason detail.
    known = {reason.code for reason in reasons}
    for code in decision.reason_codes:
        if code in known:
            continue
        source = "rule"
        if code.startswith("PROFILE_") or code.startswith("GOAL_"):
            source = "profile"
        elif code.startswith("MEMORY_"):
            source = "memory"
        elif code.startswith("BEHAVIOR_"):
            source = "behavior"
        reasons.append(
            DecisionReason(
                code=code,
                source=source,  # type: ignore[arg-type]
                priority=REASON_SOURCE_PRIORITY.get(source, 99),
                description=code,
            )
        )

    reasons.sort(key=lambda item: (item.priority, item.code))
    return reasons


def summarize_decision_sources(decision: DecisionContext) -> dict[str, int]:
    counts: dict[str, int] = {}
    for reason in collect_decision_reasons(decision):
        counts[reason.source] = counts.get(reason.source, 0) + 1
    return counts
