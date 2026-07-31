"""Pure deterministic Insight Engine."""

from __future__ import annotations

from collections.abc import Sequence

from decision.outcome import DecisionOutcomeCollection
from insights.evidence import EvidenceBasis, build_insight_evidence
from insights.models import Insight, InsightSummary
from insights.rules import (
    positive_completion_rule,
    preference_stability_rule,
    recommendation_effectiveness_rule,
    replacement_cost_rule,
    replacement_health_rule,
)
from insights.transparency import build_insight_transparency
from plan_delta.models import PlanDelta
from trends.models import TrendSummary


def _cost_deltas_available(deltas: Sequence[PlanDelta]) -> int:
    count = 0
    for delta in deltas:
        for metric in delta.metrics:
            if metric.id == "total_cost" and metric.status == "available":
                count += 1
                break
    return count


def _with_evidence(
    insight: Insight,
    basis: EvidenceBasis,
    *,
    replacement_deltas: int,
    cost_deltas_available: int,
) -> Insight:
    evidence = build_insight_evidence(
        insight,
        basis,
        replacement_deltas=replacement_deltas,
        cost_deltas_available=cost_deltas_available,
    )
    transparency = build_insight_transparency(insight, evidence)
    return insight.model_copy(
        update={"evidence": evidence, "transparency": transparency}
    )


def build_insight_summary(
    trends: TrendSummary,
    outcomes: DecisionOutcomeCollection | None,
    deltas: Sequence[PlanDelta],
    *,
    generated_at: str,
    basis: EvidenceBasis | None = None,
) -> InsightSummary:
    """Combine existing evidence without I/O, time, randomness, or LLM."""
    effective_basis = basis if basis is not None else EvidenceBasis()
    replacement_deltas = len(deltas)
    cost_available = _cost_deltas_available(deltas)
    insights = [
        replacement_health_rule(trends),
        replacement_cost_rule(trends, deltas),
        preference_stability_rule(trends),
        recommendation_effectiveness_rule(trends),
        positive_completion_rule(trends, outcomes),
    ]
    return InsightSummary(
        generated_at=generated_at,
        insights=[
            _with_evidence(
                insight,
                effective_basis,
                replacement_deltas=replacement_deltas,
                cost_deltas_available=cost_available,
            )
            for insight in insights
        ],
    )
