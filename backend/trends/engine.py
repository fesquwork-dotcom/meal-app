"""Deterministic Trend Engine.

Pure function over historical observations. No database, no cache, no clock:
``generated_at`` is injected by the caller so the same inputs always produce
the same summary.
"""

from __future__ import annotations

from collections.abc import Sequence

from trends.confidence import build_confidence
from trends.metrics import (
    AcceptedRecommendationObservation,
    WeekObservation,
    decision_health_trend,
    positive_outcome_trend,
    preference_stability_trend,
    recommendation_effectiveness_trend,
    replacement_trend,
)
from trends.models import TrendSummary


def build_trend_summary(
    observations: Sequence[WeekObservation],
    accepted_recommendations: Sequence[AcceptedRecommendationObservation],
    *,
    generated_at: str,
) -> TrendSummary:
    # Deterministic chronological order regardless of caller ordering.
    weeks = sorted(observations, key=lambda item: item.plan_start_date)
    accepted = sorted(accepted_recommendations, key=lambda item: item.accepted_on)

    metrics = [
        replacement_trend(weeks),
        positive_outcome_trend(weeks),
        decision_health_trend(weeks),
        recommendation_effectiveness_trend(weeks, accepted),
        preference_stability_trend(weeks),
    ]
    return TrendSummary(
        generated_at=generated_at,
        confidence=build_confidence(
            evidence_weeks=len(weeks), completed_strategies=len(weeks)
        ),
        metrics=metrics,
    )
