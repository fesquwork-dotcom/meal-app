"""Pure evidence builders for insights (Sprint 8.2).

No new analytics: everything here is counting of data that already exists
(week observations from the Trend layer plus already-computed plan deltas).
Coverage is a separate deterministic tier and is intentionally not tied to
Trend confidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from insights.evidence_models import (
    EvidenceCoverage,
    EvidenceCoverageStatus,
    InsightEvidence,
    InsightLimitation,
    UnavailableReason,
)
from insights.models import Insight
from trends.metrics import WeekObservation

# Coverage thresholds over completed strategies (plans).
_COMPLETE_MIN = 6
_PARTIAL_MIN = 3

# Insights whose conclusions depend on decision outcome snapshots.
_OUTCOME_DEPENDENT: frozenset[str] = frozenset(
    {"replacement_health", "preference_stability", "positive_completion"}
)


@dataclass(frozen=True)
class EvidenceBasis:
    """Aggregated once per summary from existing week observations."""

    evidence_weeks: int = 0
    completed_strategies: int = 0
    positive_events: int = 0
    replacement_events: int = 0
    decision_outcomes: int = 0
    weeks_without_outcomes: int = 0
    oldest_plan_date: str | None = None
    newest_plan_date: str | None = None
    first_positive_week_date: str | None = None
    first_outcome_week_date: str | None = None


def _positive_events(week: WeekObservation) -> int:
    return (
        week.cooked_meal_count
        + week.suited_meal_count
        + (1 if week.shopping_completed else 0)
        + (1 if week.plan_completed else 0)
    )


def _outcome_count(week: WeekObservation) -> int:
    return week.outcome_successful + week.outcome_neutral + week.outcome_unsuccessful


def build_evidence_basis(observations: Sequence[WeekObservation]) -> EvidenceBasis:
    """Count existing data; no derived metrics, no thresholds applied here."""
    if not observations:
        return EvidenceBasis()

    ordered = sorted(observations, key=lambda week: week.plan_start_date)
    first_positive = next(
        (week.plan_start_date for week in ordered if _positive_events(week) > 0),
        None,
    )
    first_outcome = next(
        (week.plan_start_date for week in ordered if _outcome_count(week) > 0),
        None,
    )
    return EvidenceBasis(
        evidence_weeks=len(ordered),
        completed_strategies=len(ordered),
        positive_events=sum(_positive_events(week) for week in ordered),
        replacement_events=sum(week.replacement_count for week in ordered),
        decision_outcomes=sum(_outcome_count(week) for week in ordered),
        weeks_without_outcomes=sum(
            1 for week in ordered if _outcome_count(week) == 0
        ),
        oldest_plan_date=ordered[0].plan_start_date,
        newest_plan_date=ordered[-1].plan_start_date,
        first_positive_week_date=first_positive,
        first_outcome_week_date=first_outcome,
    )


def coverage_status(completed_strategies: int) -> EvidenceCoverageStatus:
    if completed_strategies >= _COMPLETE_MIN:
        return "complete"
    if completed_strategies >= _PARTIAL_MIN:
        return "partial"
    return "insufficient"


def _available_since(insight: Insight, basis: EvidenceBasis) -> str | None:
    """Earliest plan date on which the insight's data actually exists."""
    if insight.id == "positive_completion":
        return basis.first_positive_week_date
    if insight.id in ("replacement_health", "preference_stability"):
        # These combine replacement/preference data with outcome snapshots;
        # the joint evidence starts when outcomes first appeared.
        return basis.first_outcome_week_date or basis.oldest_plan_date
    return basis.oldest_plan_date


def _limitations(
    insight: Insight,
    basis: EvidenceBasis,
    *,
    replacement_deltas: int,
    cost_deltas_available: int,
) -> list[InsightLimitation]:
    limitations: list[InsightLimitation] = []
    if basis.completed_strategies < _COMPLETE_MIN:
        limitations.append("not_enough_completed_plans")
    if insight.id in _OUTCOME_DEPENDENT:
        if basis.decision_outcomes == 0:
            limitations.append("outcome_snapshot_missing")
        elif basis.weeks_without_outcomes > 0:
            limitations.append("legacy_strategies")
    if insight.id == "positive_completion" and basis.positive_events == 0:
        limitations.append("positive_events_missing")
    if insight.id == "replacement_cost":
        if replacement_deltas == 0:
            limitations.append("menuplan_not_persisted")
        elif cost_deltas_available == 0:
            limitations.append("budget_data_unavailable")
    return limitations


def _unavailable_reasons(
    insight: Insight,
    basis: EvidenceBasis,
    *,
    replacement_deltas: int,
) -> list[UnavailableReason]:
    if insight.status != "insufficient_data":
        return []
    reasons: list[UnavailableReason] = []
    if basis.completed_strategies < _COMPLETE_MIN:
        reasons.append("need_more_completed_plans")
    if insight.id == "positive_completion":
        if basis.positive_events == 0:
            reasons.append("need_positive_events")
        if basis.decision_outcomes == 0:
            reasons.append("need_outcomes")
    if insight.id == "replacement_cost" and (
        replacement_deltas == 0 or basis.replacement_events == 0
    ):
        reasons.append("need_replacements")
    return reasons


def build_insight_evidence(
    insight: Insight,
    basis: EvidenceBasis,
    *,
    replacement_deltas: int = 0,
    cost_deltas_available: int = 0,
) -> InsightEvidence:
    """Attach counts, coverage and allowlisted limitations to one insight."""
    coverage = EvidenceCoverage(
        status=coverage_status(basis.completed_strategies),
        available_since=_available_since(insight, basis),
        oldest_plan_date=basis.oldest_plan_date,
        newest_plan_date=basis.newest_plan_date,
    )
    return InsightEvidence(
        sources=list(insight.evidence.sources),
        evidence_weeks=basis.evidence_weeks,
        completed_strategies=basis.completed_strategies,
        positive_events=basis.positive_events,
        replacement_events=basis.replacement_events,
        decision_outcomes=basis.decision_outcomes,
        coverage=coverage,
        limitations=_limitations(
            insight,
            basis,
            replacement_deltas=replacement_deltas,
            cost_deltas_available=cost_deltas_available,
        ),
        unavailable_reasons=_unavailable_reasons(
            insight,
            basis,
            replacement_deltas=replacement_deltas,
        ),
    )
