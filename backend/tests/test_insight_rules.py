"""Insight rules v1 and honesty gates."""

from __future__ import annotations

from decision.outcome import DecisionOutcome, DecisionOutcomeCollection
from insights.engine import build_insight_summary
from plan_delta.models import PlanDelta, PlanDeltaMetric
from trends.confidence import build_confidence
from trends.models import METRIC_AVAILABILITY, TrendMetric, TrendSummary
from trends.presentation import METRIC_SOURCES, METRIC_TITLES, summary_text


def _metric(metric_id, status, *, established=True):
    confidence = build_confidence(
        evidence_weeks=6 if established else 3,
        completed_strategies=6,
    )
    return TrendMetric(
        id=metric_id,
        title=METRIC_TITLES[metric_id],
        status=status,
        value=None,
        change=None,
        evidence_weeks=confidence.weeks,
        confidence=confidence,
        source=METRIC_SOURCES[metric_id],
        available_since=METRIC_AVAILABILITY[metric_id],
        summary_text=summary_text(metric_id, status, confidence.status),
    )


def _trends(**statuses) -> TrendSummary:
    defaults = {
        "replacement_rate": "stable",
        "positive_completion": "stable",
        "decision_health": "stable",
        "recommendation_effectiveness": "stable",
        "preference_stability": "stable",
    }
    defaults.update(statuses)
    return TrendSummary(
        generated_at="2026-07-15T12:00:00+00:00",
        confidence=build_confidence(evidence_weeks=6, completed_strategies=6),
        metrics=[
            _metric(metric_id, status)
            for metric_id, status in defaults.items()
        ],
    )


def _cost_delta(direction: str) -> PlanDelta:
    values = {
        "decreased": (2700, 2450, -250),
        "increased": (2700, 2900, 200),
        "unchanged": (2700, 2700, 0),
    }
    original, current, delta = values[direction]
    return PlanDelta(
        metrics=[
            PlanDeltaMetric(
                id="total_cost",
                status="available",
                unit="rub",
                original=original,
                current=current,
                delta=delta,
                direction=direction,
            )
        ]
    )


def _outcomes(successful=True) -> DecisionOutcomeCollection:
    return DecisionOutcomeCollection(
        outcomes=[
            DecisionOutcome(
                decision_key="shopping.days",
                result="shopping_completed_confirmed",
                confidence="strong",
                evidence_count=1,
                status="successful" if successful else "neutral",
            )
        ]
    )


def _by_id(summary, insight_id):
    return next(item for item in summary.insights if item.id == insight_id)


def test_replacement_health_requires_two_established_improving_trends():
    summary = build_insight_summary(
        _trends(replacement_rate="improving", decision_health="improving"),
        None,
        [],
        generated_at="2026-07-15T12:00:00+00:00",
    )
    insight = _by_id(summary, "replacement_health")
    assert insight.status == "confirmed"
    assert insight.summary == "Замен стало меньше."
    assert insight.confidence.level == "high"
    assert insight.evidence.sources == [
        "trend.replacement_rate",
        "trend.decision_health",
    ]


def test_replacement_health_rejects_emerging_or_worsening_health():
    trends = _trends(replacement_rate="improving", decision_health="worsening")
    assert _by_id(
        build_insight_summary(
            trends, None, [], generated_at="2026-07-15T12:00:00+00:00"
        ),
        "replacement_health",
    ).status == "insufficient_data"

    emerging = trends.model_copy(
        update={
            "metrics": [
                metric.model_copy(
                    update={"confidence": build_confidence(
                        evidence_weeks=3, completed_strategies=6
                    )}
                )
                if metric.id == "replacement_rate"
                else metric
                for metric in trends.metrics
            ]
        }
    )
    assert _by_id(
        build_insight_summary(
            emerging, None, [], generated_at="2026-07-15T12:00:00+00:00"
        ),
        "replacement_health",
    ).status == "insufficient_data"


def test_cost_rule_requires_three_deltas_and_strict_majority_decreased():
    trends = _trends(replacement_rate="improving")
    confirmed = build_insight_summary(
        trends,
        None,
        [_cost_delta("decreased"), _cost_delta("decreased"), _cost_delta("unchanged")],
        generated_at="2026-07-15T12:00:00+00:00",
    )
    insight = _by_id(confirmed, "replacement_cost")
    assert insight.status == "confirmed"
    assert insight.summary == "После замен стоимость плана обычно уменьшается."

    too_few = build_insight_summary(
        trends,
        None,
        [_cost_delta("decreased")],
        generated_at="2026-07-15T12:00:00+00:00",
    )
    assert _by_id(too_few, "replacement_cost").status == "insufficient_data"

    no_majority = build_insight_summary(
        trends,
        None,
        [_cost_delta("decreased"), _cost_delta("increased"), _cost_delta("unchanged")],
        generated_at="2026-07-15T12:00:00+00:00",
    )
    assert _by_id(no_majority, "replacement_cost").status == "insufficient_data"


def test_preference_stability_reuses_trend_text():
    summary = build_insight_summary(
        _trends(preference_stability="stable", decision_health="improving"),
        None,
        [],
        generated_at="2026-07-15T12:00:00+00:00",
    )
    insight = _by_id(summary, "preference_stability")
    assert insight.status == "confirmed"
    assert insight.summary == "Настройки остаются стабильными."


def test_recommendation_effectiveness_requires_established_improvement():
    summary = build_insight_summary(
        _trends(recommendation_effectiveness="improving"),
        None,
        [],
        generated_at="2026-07-15T12:00:00+00:00",
    )
    insight = _by_id(summary, "recommendation_effectiveness")
    assert insight.status == "confirmed"
    assert insight.summary == "После принятой рекомендации замен стало меньше."


def test_positive_completion_requires_trend_and_successful_outcome():
    trends = _trends(positive_completion="improving")
    confirmed = build_insight_summary(
        trends,
        _outcomes(),
        [],
        generated_at="2026-07-15T12:00:00+00:00",
    )
    insight = _by_id(confirmed, "positive_completion")
    assert insight.status == "confirmed"
    assert insight.summary == "Подтверждённых успехов стало больше."

    without_outcome = build_insight_summary(
        trends, None, [], generated_at="2026-07-15T12:00:00+00:00"
    )
    assert _by_id(
        without_outcome, "positive_completion"
    ).status == "insufficient_data"

