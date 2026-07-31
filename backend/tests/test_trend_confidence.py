"""Confidence gate: the most important invariant of Sprint 7.1."""

from trends.confidence import (
    EMERGING_MIN_WEEKS,
    ESTABLISHED_MIN_WEEKS,
    build_confidence,
    confidence_status,
)
from trends.metrics import WeekObservation, replacement_trend


def _week(index: int, *, replacements: int = 0) -> WeekObservation:
    return WeekObservation(
        plan_start_date=f"2026-{(index // 28) + 1:02d}-{(index % 28) + 1:02d}",
        planned_meal_count=21,
        replacement_count=replacements,
        cooked_meal_count=0,
        suited_meal_count=0,
        shopping_completed=False,
        plan_completed=False,
        outcome_successful=0,
        outcome_neutral=0,
        outcome_unsuccessful=0,
        has_outcomes=False,
        preference_fingerprint="stable",
    )


def test_confidence_thresholds():
    assert confidence_status(0) == "insufficient_data"
    assert confidence_status(2) == "insufficient_data"
    assert confidence_status(EMERGING_MIN_WEEKS) == "emerging"
    assert confidence_status(4) == "emerging"
    assert confidence_status(ESTABLISHED_MIN_WEEKS) == "established"
    assert confidence_status(8) == "established"


def test_build_confidence_clamps_negative_counts():
    confidence = build_confidence(evidence_weeks=-1, completed_strategies=-5)
    assert confidence.weeks == 0
    assert confidence.completed_strategies == 0
    assert confidence.status == "insufficient_data"


def test_quantitative_fields_only_when_established():
    two_weeks = [_week(0, replacements=10), _week(1, replacements=1)]
    metric = replacement_trend(two_weeks)
    assert metric.confidence.status == "insufficient_data"
    assert metric.status == "insufficient_data"
    assert metric.value is None
    assert metric.change is None

    four_weeks = [
        _week(0, replacements=10),
        _week(1, replacements=10),
        _week(2, replacements=1),
        _week(3, replacements=1),
    ]
    emerging = replacement_trend(four_weeks)
    assert emerging.confidence.status == "emerging"
    assert emerging.status == "improving"
    # Emerging metrics stay qualitative.
    assert emerging.value is None
    assert emerging.change is None
    assert emerging.summary_text == "Есть первые признаки улучшения."

    eight_weeks = [
        _week(index, replacements=10 if index < 4 else 1) for index in range(8)
    ]
    established = replacement_trend(eight_weeks)
    assert established.confidence.status == "established"
    assert established.status == "improving"
    assert established.value is not None
    assert established.change is not None
    assert established.change < 0


def test_insufficient_data_text_is_qualitative():
    metric = replacement_trend([_week(0)])
    assert metric.summary_text == "Пока недостаточно данных."
