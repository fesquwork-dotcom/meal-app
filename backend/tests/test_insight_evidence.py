"""Evidence basis counting, coverage tiers, and allowlisted limitations."""

from __future__ import annotations

import pathlib
from typing import get_args

from insights.evidence import (
    EvidenceBasis,
    build_evidence_basis,
    build_insight_evidence,
    coverage_status,
)
from insights.evidence_models import InsightLimitation, UnavailableReason
from insights.models import Insight, InsightConfidence, InsightEvidence
from trends.metrics import WeekObservation


def _week(
    start: str,
    *,
    replacements: int = 0,
    cooked: int = 0,
    suited: int = 0,
    shopping: bool = False,
    plan: bool = False,
    successful: int = 0,
    neutral: int = 0,
    unsuccessful: int = 0,
) -> WeekObservation:
    outcome_total = successful + neutral + unsuccessful
    return WeekObservation(
        plan_start_date=start,
        planned_meal_count=14,
        replacement_count=replacements,
        cooked_meal_count=cooked,
        suited_meal_count=suited,
        shopping_completed=shopping,
        plan_completed=plan,
        outcome_successful=successful,
        outcome_neutral=neutral,
        outcome_unsuccessful=unsuccessful,
        has_outcomes=outcome_total > 0,
        preference_fingerprint="fp",
    )


def _insight(
    insight_id: str,
    *,
    status: str = "insufficient_data",
    sources: list[str] | None = None,
) -> Insight:
    return Insight(
        id=insight_id,
        title="t",
        summary="s",
        category="progress",
        confidence=InsightConfidence(level="low", basis="none"),
        status=status,
        evidence=InsightEvidence(sources=sources or ["trend.replacement_rate"]),
        available_since="sprint_7_1",
    )


def test_basis_counts_only_existing_data():
    basis = build_evidence_basis(
        [
            _week("2026-06-08", replacements=2),
            _week(
                "2026-06-01",
                cooked=3,
                suited=1,
                shopping=True,
                plan=True,
                successful=2,
                neutral=1,
            ),
            _week("2026-06-15", replacements=1, cooked=2, successful=1),
        ]
    )
    assert basis.evidence_weeks == 3
    assert basis.completed_strategies == 3
    assert basis.replacement_events == 3
    # 3+1+1+1 (first) + 2 (last)
    assert basis.positive_events == 8
    assert basis.decision_outcomes == 4
    assert basis.weeks_without_outcomes == 1
    assert basis.oldest_plan_date == "2026-06-01"
    assert basis.newest_plan_date == "2026-06-15"
    assert basis.first_positive_week_date == "2026-06-01"
    assert basis.first_outcome_week_date == "2026-06-01"


def test_empty_observations_give_empty_basis():
    assert build_evidence_basis([]) == EvidenceBasis()


def test_coverage_thresholds_are_deterministic():
    assert coverage_status(0) == "insufficient"
    assert coverage_status(2) == "insufficient"
    assert coverage_status(3) == "partial"
    assert coverage_status(5) == "partial"
    assert coverage_status(6) == "complete"
    assert coverage_status(12) == "complete"


def test_available_since_is_later_for_outcome_dependent_insights():
    basis = build_evidence_basis(
        [
            _week("2026-05-01", replacements=1),
            _week("2026-05-08", replacements=1),
            _week("2026-05-15", successful=1, cooked=1),
        ]
    )
    outcome_dependent = build_insight_evidence(
        _insight("replacement_health"), basis
    )
    assert outcome_dependent.coverage.available_since == "2026-05-15"
    history_based = build_insight_evidence(_insight("replacement_cost"), basis)
    assert history_based.coverage.available_since == "2026-05-01"


def test_limitations_are_allowlisted_and_deterministic():
    basis = build_evidence_basis(
        [
            _week("2026-06-01", replacements=1),
            _week("2026-06-08", successful=1, cooked=1),
        ]
    )
    evidence = build_insight_evidence(_insight("replacement_health"), basis)
    assert evidence.limitations == ["not_enough_completed_plans", "legacy_strategies"]

    no_outcomes = build_evidence_basis([_week("2026-06-01", replacements=1)])
    evidence = build_insight_evidence(_insight("positive_completion"), no_outcomes)
    assert "outcome_snapshot_missing" in evidence.limitations
    assert "positive_events_missing" in evidence.limitations

    cost_no_plans = build_insight_evidence(
        _insight("replacement_cost"), no_outcomes, replacement_deltas=0
    )
    assert "menuplan_not_persisted" in cost_no_plans.limitations

    cost_no_budget = build_insight_evidence(
        _insight("replacement_cost"),
        no_outcomes,
        replacement_deltas=2,
        cost_deltas_available=0,
    )
    assert "budget_data_unavailable" in cost_no_budget.limitations

    allowed_limitations = set(get_args(InsightLimitation))
    for built in (evidence, cost_no_plans, cost_no_budget):
        assert set(built.limitations) <= allowed_limitations


def test_unavailable_reasons_only_for_insufficient_insights():
    basis = build_evidence_basis([_week("2026-06-01", replacements=1)])
    insufficient = build_insight_evidence(
        _insight("positive_completion"), basis
    )
    assert insufficient.unavailable_reasons == [
        "need_more_completed_plans",
        "need_positive_events",
        "need_outcomes",
    ]
    assert set(insufficient.unavailable_reasons) <= set(get_args(UnavailableReason))

    confirmed = build_insight_evidence(
        _insight("positive_completion", status="confirmed"), basis
    )
    assert confirmed.unavailable_reasons == []


def test_replacement_cost_needs_replacements():
    basis = build_evidence_basis([_week("2026-06-01")])
    evidence = build_insight_evidence(
        _insight("replacement_cost"), basis, replacement_deltas=0
    )
    assert "need_replacements" in evidence.unavailable_reasons


def test_evidence_preserves_sources_and_counts():
    basis = build_evidence_basis(
        [_week(f"2026-06-{day:02d}", replacements=1, successful=1) for day in range(1, 8)]
    )
    insight = _insight(
        "replacement_health",
        status="confirmed",
        sources=["trend.replacement_rate", "trend.decision_health"],
    )
    evidence = build_insight_evidence(insight, basis)
    assert evidence.version == 1
    assert evidence.sources == ["trend.replacement_rate", "trend.decision_health"]
    assert evidence.completed_strategies == 7
    assert evidence.coverage.status == "complete"
    assert evidence.limitations == []
    assert evidence.unavailable_reasons == []


def test_evidence_modules_are_pure():
    package_dir = pathlib.Path(__file__).resolve().parents[1] / "insights"
    for module in ("evidence.py", "evidence_models.py", "transparency.py"):
        source = (package_dir / module).read_text(encoding="utf-8")
        for forbidden in (
            "aiosqlite",
            "import database",
            "datetime.now",
            "import random",
            "anthropic",
            "openai",
        ):
            assert forbidden not in source, f"{module} must stay pure: {forbidden}"
