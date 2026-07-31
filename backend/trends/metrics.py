"""Pure per-metric computations for the Trend Engine.

Inputs are pre-aggregated week observations (one per finalized strategy).
No database access, no clock, no randomness — same input, same output.
"""

from __future__ import annotations

from dataclasses import dataclass

from trends.confidence import build_confidence
from trends.models import (
    METRIC_AVAILABILITY,
    MetricId,
    TrendConfidence,
    TrendMetric,
    TrendMetricStatus,
)
from trends.presentation import (
    CAPABILITY_NOTE,
    METRIC_SOURCES,
    METRIC_TITLES,
    format_percent,
    summary_text,
)

# Minimum absolute rate delta between windows to call a direction.
STABLE_RATE_DELTA = 0.05
# Share of week-to-week setting changes above which preferences are volatile.
VOLATILE_CHANGE_SHARE = 1 / 3


@dataclass(frozen=True)
class WeekObservation:
    """Aggregates for one finalized strategy week. Internal only, never exposed."""

    plan_start_date: str
    planned_meal_count: int
    replacement_count: int
    cooked_meal_count: int
    suited_meal_count: int
    shopping_completed: bool
    plan_completed: bool
    outcome_successful: int
    outcome_neutral: int
    outcome_unsuccessful: int
    has_outcomes: bool
    preference_fingerprint: str


@dataclass(frozen=True)
class AcceptedRecommendationObservation:
    """Date-only view of an accepted learning recommendation."""

    accepted_on: str  # ISO date (YYYY-MM-DD)


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _split_windows(values: list[float]) -> tuple[list[float], list[float]]:
    """Earlier half vs recent half (recent gets the extra week when odd)."""
    midpoint = len(values) // 2
    return values[:midpoint], values[midpoint:]


def _direction(
    earlier_avg: float, recent_avg: float, *, lower_is_better: bool
) -> TrendMetricStatus:
    delta = recent_avg - earlier_avg
    if abs(delta) < STABLE_RATE_DELTA:
        return "stable"
    improved = delta < 0 if lower_is_better else delta > 0
    return "improving" if improved else "worsening"


def _relative_change(earlier_avg: float, recent_avg: float) -> int | None:
    if earlier_avg <= 0:
        return None
    change = round((recent_avg - earlier_avg) / earlier_avg * 100)
    return max(-100, min(1000, change))


def _metric(
    metric_id: MetricId,
    *,
    status: TrendMetricStatus,
    confidence: TrendConfidence,
    evidence_weeks: int,
    value: str | None = None,
    change: int | None = None,
    capability_limited: bool = False,
) -> TrendMetric:
    # Confidence gate: quantitative fields exist only for established metrics.
    if confidence.status != "established":
        value = None
        change = None
    if confidence.status == "insufficient_data":
        status = "insufficient_data"
    return TrendMetric(
        id=metric_id,
        title=METRIC_TITLES[metric_id],
        status=status,
        value=value,
        change=change,
        evidence_weeks=evidence_weeks,
        confidence=confidence,
        source=METRIC_SOURCES[metric_id],
        available_since=METRIC_AVAILABILITY[metric_id],
        summary_text=summary_text(metric_id, status, confidence.status),
        capability_note=CAPABILITY_NOTE if capability_limited else None,
    )


def _rate_trend_metric(
    metric_id: MetricId,
    rates: list[float],
    *,
    completed_strategies: int,
    lower_is_better: bool,
    capability_limited: bool = False,
) -> TrendMetric:
    confidence = build_confidence(
        evidence_weeks=len(rates), completed_strategies=completed_strategies
    )
    if len(rates) < 2:
        return _metric(
            metric_id,
            status="insufficient_data",
            confidence=confidence,
            evidence_weeks=len(rates),
            capability_limited=capability_limited,
        )
    earlier, recent = _split_windows(rates)
    earlier_avg = _average(earlier)
    recent_avg = _average(recent)
    return _metric(
        metric_id,
        status=_direction(earlier_avg, recent_avg, lower_is_better=lower_is_better),
        confidence=confidence,
        evidence_weeks=len(rates),
        value=format_percent(recent_avg),
        change=_relative_change(earlier_avg, recent_avg),
        capability_limited=capability_limited,
    )


def _replacement_rate(week: WeekObservation) -> float:
    if week.planned_meal_count <= 0:
        return 0.0
    return min(1.0, week.replacement_count / week.planned_meal_count)


def replacement_trend(weeks: list[WeekObservation]) -> TrendMetric:
    rates = [_replacement_rate(week) for week in weeks]
    return _rate_trend_metric(
        "replacement_rate",
        rates,
        completed_strategies=len(weeks),
        lower_is_better=True,
    )


def _positive_completion_rate(week: WeekObservation) -> float:
    total_units = week.planned_meal_count + 2  # meals + shopping + plan marks
    if total_units <= 0:
        return 0.0
    # A meal is confirmed once regardless of how many marks it received.
    confirmed_meals = min(
        week.planned_meal_count,
        max(week.cooked_meal_count, week.suited_meal_count),
    )
    confirmed = (
        confirmed_meals
        + (1 if week.shopping_completed else 0)
        + (1 if week.plan_completed else 0)
    )
    return min(1.0, confirmed / total_units)


def _has_positive_marks(week: WeekObservation) -> bool:
    return (
        week.cooked_meal_count > 0
        or week.suited_meal_count > 0
        or week.shopping_completed
        or week.plan_completed
    )


def positive_outcome_trend(weeks: list[WeekObservation]) -> TrendMetric:
    # Capability gate: only weeks where explicit marks exist can contribute.
    marked_weeks = [week for week in weeks if _has_positive_marks(week)]
    rates = [_positive_completion_rate(week) for week in marked_weeks]
    return _rate_trend_metric(
        "positive_completion",
        rates,
        completed_strategies=len(weeks),
        lower_is_better=False,
        capability_limited=len(marked_weeks) < len(weeks),
    )


def _decision_health_rate(week: WeekObservation) -> float:
    evaluated = (
        week.outcome_successful + week.outcome_neutral + week.outcome_unsuccessful
    )
    if evaluated <= 0:
        return 0.0
    return week.outcome_successful / evaluated


def decision_health_trend(weeks: list[WeekObservation]) -> TrendMetric:
    evaluated_weeks = [
        week
        for week in weeks
        if week.has_outcomes
        and (
            week.outcome_successful
            + week.outcome_neutral
            + week.outcome_unsuccessful
        )
        > 0
    ]
    rates = [_decision_health_rate(week) for week in evaluated_weeks]
    return _rate_trend_metric(
        "decision_health",
        rates,
        completed_strategies=len(weeks),
        lower_is_better=False,
        capability_limited=len(evaluated_weeks) < len(weeks),
    )


def recommendation_effectiveness_trend(
    weeks: list[WeekObservation],
    accepted: list[AcceptedRecommendationObservation],
) -> TrendMetric:
    accepted_dates = sorted(item.accepted_on for item in accepted)
    if not accepted_dates:
        confidence = build_confidence(
            evidence_weeks=0, completed_strategies=len(weeks)
        )
        return _metric(
            "recommendation_effectiveness",
            status="insufficient_data",
            confidence=confidence,
            evidence_weeks=0,
            capability_limited=bool(weeks),
        )
    first_accepted = accepted_dates[0]
    before = [week for week in weeks if week.plan_start_date < first_accepted]
    after = [week for week in weeks if week.plan_start_date >= first_accepted]
    # Confidence counts only post-acceptance weeks: that is the observation
    # window in which the recommendation could have had an effect.
    confidence = build_confidence(
        evidence_weeks=len(after), completed_strategies=len(weeks)
    )
    if not before or not after:
        return _metric(
            "recommendation_effectiveness",
            status="insufficient_data",
            confidence=confidence,
            evidence_weeks=len(after),
        )
    before_avg = _average([_replacement_rate(week) for week in before])
    after_avg = _average([_replacement_rate(week) for week in after])
    return _metric(
        "recommendation_effectiveness",
        status=_direction(before_avg, after_avg, lower_is_better=True),
        confidence=confidence,
        evidence_weeks=len(after),
        value=format_percent(after_avg),
        change=_relative_change(before_avg, after_avg),
    )


def preference_stability_trend(weeks: list[WeekObservation]) -> TrendMetric:
    confidence = build_confidence(
        evidence_weeks=len(weeks), completed_strategies=len(weeks)
    )
    if len(weeks) < 2:
        return _metric(
            "preference_stability",
            status="insufficient_data",
            confidence=confidence,
            evidence_weeks=len(weeks),
        )
    changes = sum(
        1
        for previous, current in zip(weeks, weeks[1:])
        if previous.preference_fingerprint != current.preference_fingerprint
    )
    change_share = changes / (len(weeks) - 1)
    status: TrendMetricStatus = (
        "volatile" if change_share > VOLATILE_CHANGE_SHARE else "stable"
    )
    return _metric(
        "preference_stability",
        status=status,
        confidence=confidence,
        evidence_weeks=len(weeks),
        # Qualitative metric: no percentage even when established.
        value=None,
        change=None,
    )
