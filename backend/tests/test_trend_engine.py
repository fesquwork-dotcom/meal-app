"""Pure Trend Engine: determinism, directions, capability, isolation."""

import pathlib

from trends.engine import build_trend_summary
from trends.metrics import (
    AcceptedRecommendationObservation,
    WeekObservation,
    decision_health_trend,
    positive_outcome_trend,
    preference_stability_trend,
    recommendation_effectiveness_trend,
)
from trends.models import TREND_VERSION

GENERATED_AT = "2026-07-14T00:00:00+00:00"


def _week(
    index: int,
    *,
    replacements: int = 0,
    cooked: int = 0,
    suited: int = 0,
    shopping: bool = False,
    plan: bool = False,
    successful: int = 0,
    unsuccessful: int = 0,
    has_outcomes: bool = False,
    fingerprint: str = "stable",
) -> WeekObservation:
    return WeekObservation(
        plan_start_date=f"2026-{(index // 28) + 1:02d}-{(index % 28) + 1:02d}",
        planned_meal_count=21,
        replacement_count=replacements,
        cooked_meal_count=cooked,
        suited_meal_count=suited,
        shopping_completed=shopping,
        plan_completed=plan,
        outcome_successful=successful,
        outcome_neutral=0,
        outcome_unsuccessful=unsuccessful,
        has_outcomes=has_outcomes,
        preference_fingerprint=fingerprint,
    )


def test_empty_history_yields_insufficient_summary():
    summary = build_trend_summary([], [], generated_at=GENERATED_AT)
    assert summary.version == TREND_VERSION
    assert summary.generated_at == GENERATED_AT
    assert summary.confidence.status == "insufficient_data"
    assert len(summary.metrics) == 5
    assert {metric.status for metric in summary.metrics} == {"insufficient_data"}
    assert all(metric.value is None and metric.change is None for metric in summary.metrics)


def test_engine_is_deterministic_and_order_independent():
    weeks = [_week(index, replacements=index) for index in range(8)]
    accepted = [AcceptedRecommendationObservation(accepted_on="2026-01-05")]
    first = build_trend_summary(weeks, accepted, generated_at=GENERATED_AT)
    second = build_trend_summary(
        list(reversed(weeks)), accepted, generated_at=GENERATED_AT
    )
    assert first == second


def test_worsening_replacements_detected():
    weeks = [
        _week(index, replacements=1 if index < 4 else 12) for index in range(8)
    ]
    summary = build_trend_summary(weeks, [], generated_at=GENERATED_AT)
    replacement = next(m for m in summary.metrics if m.id == "replacement_rate")
    assert replacement.status == "worsening"
    assert replacement.change is not None and replacement.change > 0
    assert replacement.summary_text == "Замен стало больше."


def test_positive_completion_uses_only_marked_weeks_and_notes_capability():
    weeks = [_week(index) for index in range(4)] + [
        _week(index, cooked=5, suited=4, shopping=True, plan=True)
        for index in range(4, 8)
    ]
    metric = positive_outcome_trend(weeks)
    assert metric.evidence_weeks == 4
    assert metric.confidence.status == "emerging"
    assert metric.capability_note is not None
    assert "после обновления приложения" in metric.capability_note


def test_decision_health_counts_only_evaluated_weeks():
    weeks = [
        _week(0, successful=1, unsuccessful=3, has_outcomes=True),
        _week(1, successful=1, unsuccessful=3, has_outcomes=True),
        _week(2),
        _week(3, successful=4, unsuccessful=0, has_outcomes=True),
        _week(4, successful=4, unsuccessful=0, has_outcomes=True),
    ]
    metric = decision_health_trend(weeks)
    assert metric.evidence_weeks == 4
    assert metric.status == "improving"
    assert metric.capability_note is not None


def test_recommendation_effectiveness_compares_before_and_after():
    weeks = [
        _week(index, replacements=12 if index < 4 else 1) for index in range(8)
    ]
    accepted = [
        AcceptedRecommendationObservation(accepted_on=weeks[4].plan_start_date)
    ]
    metric = recommendation_effectiveness_trend(weeks, accepted)
    assert metric.status == "improving"
    assert metric.evidence_weeks == 4  # only post-acceptance weeks count

    without_accepted = recommendation_effectiveness_trend(weeks, [])
    assert without_accepted.status == "insufficient_data"
    assert without_accepted.evidence_weeks == 0


def test_preference_stability_classifies_volatile_and_stable():
    stable_weeks = [_week(index, fingerprint="same") for index in range(8)]
    stable = preference_stability_trend(stable_weeks)
    assert stable.status == "stable"
    assert stable.value is None and stable.change is None
    assert stable.summary_text == "Настройки остаются стабильными."

    volatile_weeks = [_week(index, fingerprint=f"v{index}") for index in range(8)]
    volatile = preference_stability_trend(volatile_weeks)
    assert volatile.status == "volatile"
    assert volatile.summary_text == "Настройки меняются часто."


def test_metric_capability_declared_for_every_metric():
    summary = build_trend_summary(
        [_week(index) for index in range(3)], [], generated_at=GENERATED_AT
    )
    by_id = {metric.id: metric for metric in summary.metrics}
    assert by_id["replacement_rate"].available_since == "phase_1"
    assert by_id["decision_health"].available_since == "sprint_6_4"
    assert by_id["positive_completion"].available_since == "sprint_6_5"
    assert by_id["recommendation_effectiveness"].available_since == "sprint_6_6"
    assert by_id["preference_stability"].available_since == "phase_1"


def test_trend_engine_is_pure_and_isolated():
    trends_dir = pathlib.Path(__file__).resolve().parents[1] / "trends"
    for module in ("engine.py", "metrics.py", "confidence.py", "models.py"):
        source = (trends_dir / module).read_text(encoding="utf-8")
        for forbidden in (
            "aiosqlite",
            "import database",
            "datetime.now",
            "import random",
        ):
            assert forbidden not in source, f"{module} must stay pure: {forbidden}"


def test_decision_and_learning_layers_do_not_import_trends():
    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    for package in ("decision", "learning", "strategy"):
        for path in (backend_dir / package).glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "trends" not in source, f"{path} must not depend on trends"
