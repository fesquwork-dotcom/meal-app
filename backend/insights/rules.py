"""Insight rules v1.

Each rule consumes existing domain models only. Rules never query storage,
never inspect raw events, and never invent confidence beyond source tiers.
"""

from __future__ import annotations

from collections.abc import Sequence

from decision.outcome import DecisionOutcomeCollection
from insights.models import (
    Insight,
    InsightConfidence,
    InsightEvidence,
    InsightEvidenceSource,
    InsightId,
)
from insights.presentation import (
    COST_DECREASE_SUMMARY,
    INSUFFICIENT_SUMMARIES,
    INSIGHT_TITLES,
)
from plan_delta.models import PlanDelta
from trends.models import MetricId, TrendMetric, TrendSummary


def _trend_metric(summary: TrendSummary, metric_id: MetricId) -> TrendMetric | None:
    return next((item for item in summary.metrics if item.id == metric_id), None)


def _insufficient(
    insight_id: InsightId,
    *,
    category: str,
    sources: list[InsightEvidenceSource],
    available_since: str,
) -> Insight:
    return Insight(
        id=insight_id,
        title=INSIGHT_TITLES[insight_id],
        summary=INSUFFICIENT_SUMMARIES[insight_id],
        category=category,
        confidence=InsightConfidence(level="low", basis="none"),
        status="insufficient_data",
        evidence=InsightEvidence(sources=sources),
        available_since=available_since,
    )


def _confirmed_from_trend(
    insight_id: InsightId,
    *,
    category: str,
    summary: str,
    sources: list[InsightEvidenceSource],
    available_since: str,
) -> Insight:
    # Every confirmed v1 rule requires an established TrendMetric. Therefore
    # high confidence is copied from that existing tier, not recalculated.
    return Insight(
        id=insight_id,
        title=INSIGHT_TITLES[insight_id],
        summary=summary,
        category=category,
        confidence=InsightConfidence(level="high", basis="trend"),
        status="confirmed",
        evidence=InsightEvidence(sources=sources),
        available_since=available_since,
    )


def replacement_health_rule(trends: TrendSummary) -> Insight:
    replacement = _trend_metric(trends, "replacement_rate")
    health = _trend_metric(trends, "decision_health")
    sources: list[InsightEvidenceSource] = [
        "trend.replacement_rate",
        "trend.decision_health",
    ]
    if (
        replacement is not None
        and health is not None
        and replacement.confidence.status == "established"
        and health.confidence.status == "established"
        and replacement.status == "improving"
        and health.status == "improving"
    ):
        # Reuse the allowlisted Trend presentation instead of copying it.
        return _confirmed_from_trend(
            "replacement_health",
            category="progress",
            summary=replacement.summary_text,
            sources=sources,
            available_since="sprint_7_1",
        )
    return _insufficient(
        "replacement_health",
        category="progress",
        sources=sources,
        available_since="sprint_7_1",
    )


def replacement_cost_rule(
    trends: TrendSummary, deltas: Sequence[PlanDelta]
) -> Insight:
    replacement = _trend_metric(trends, "replacement_rate")
    sources: list[InsightEvidenceSource] = [
        "trend.replacement_rate",
        "delta.total_cost",
    ]
    cost_metrics = [
        metric
        for delta in deltas
        for metric in delta.metrics
        if metric.id == "total_cost" and metric.status == "available"
    ]
    decreases = sum(metric.direction == "decreased" for metric in cost_metrics)
    if (
        replacement is not None
        and replacement.confidence.status == "established"
        and replacement.status == "improving"
        # "Usually" requires multiple comparable plans and a strict majority.
        and len(cost_metrics) >= 3
        and decreases > len(cost_metrics) / 2
    ):
        return _confirmed_from_trend(
            "replacement_cost",
            category="cost",
            summary=COST_DECREASE_SUMMARY,
            sources=sources,
            available_since="sprint_7_4",
        )
    return _insufficient(
        "replacement_cost",
        category="cost",
        sources=sources,
        available_since="sprint_7_4",
    )


def preference_stability_rule(trends: TrendSummary) -> Insight:
    stability = _trend_metric(trends, "preference_stability")
    health = _trend_metric(trends, "decision_health")
    sources: list[InsightEvidenceSource] = [
        "trend.preference_stability",
        "trend.decision_health",
    ]
    if (
        stability is not None
        and health is not None
        and stability.confidence.status == "established"
        and health.confidence.status == "established"
        and stability.status == "stable"
        and health.status in {"improving", "stable"}
    ):
        return _confirmed_from_trend(
            "preference_stability",
            category="consistency",
            summary=stability.summary_text,
            sources=sources,
            available_since="sprint_7_1",
        )
    return _insufficient(
        "preference_stability",
        category="consistency",
        sources=sources,
        available_since="sprint_7_1",
    )


def recommendation_effectiveness_rule(trends: TrendSummary) -> Insight:
    effectiveness = _trend_metric(trends, "recommendation_effectiveness")
    sources: list[InsightEvidenceSource] = [
        "trend.recommendation_effectiveness"
    ]
    if (
        effectiveness is not None
        and effectiveness.confidence.status == "established"
        and effectiveness.status == "improving"
    ):
        return _confirmed_from_trend(
            "recommendation_effectiveness",
            category="adaptation",
            summary=effectiveness.summary_text,
            sources=sources,
            available_since="sprint_6_6",
        )
    return _insufficient(
        "recommendation_effectiveness",
        category="adaptation",
        sources=sources,
        available_since="sprint_6_6",
    )


def positive_completion_rule(
    trends: TrendSummary, outcomes: DecisionOutcomeCollection | None
) -> Insight:
    completion = _trend_metric(trends, "positive_completion")
    sources: list[InsightEvidenceSource] = [
        "trend.positive_completion",
        "outcome.successful",
    ]
    has_successful_outcome = bool(
        outcomes
        and any(outcome.status == "successful" for outcome in outcomes.outcomes)
    )
    if (
        completion is not None
        and completion.confidence.status == "established"
        and completion.status == "improving"
        and has_successful_outcome
    ):
        return _confirmed_from_trend(
            "positive_completion",
            category="planning",
            summary=completion.summary_text,
            sources=sources,
            available_since="sprint_6_4",
        )
    return _insufficient(
        "positive_completion",
        category="planning",
        sources=sources,
        available_since="sprint_6_4",
    )

