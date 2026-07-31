"""Transparency builder: allowlisted texts only, no free-form strings."""

from __future__ import annotations

import re

from insights.evidence_models import EvidenceCoverage, InsightEvidence
from insights.models import Insight, InsightConfidence
from insights.transparency import (
    AVAILABILITY_LIMITED_TEXT,
    COVERAGE_TEXTS,
    LIMITATION_TEXTS,
    PROOF_COLLECTING_TEXT,
    TRANSPARENCY_TITLE,
    build_insight_transparency,
)


def _insight() -> Insight:
    return Insight(
        id="replacement_health",
        title="t",
        summary="s",
        category="progress",
        confidence=InsightConfidence(level="high", basis="trend"),
        status="confirmed",
        evidence=InsightEvidence(sources=["trend.replacement_rate"]),
        available_since="sprint_7_1",
    )


def _evidence(
    *,
    status: str = "complete",
    completed: int = 8,
    limitations: list[str] | None = None,
    available_since: str | None = "2026-05-01",
    oldest: str | None = "2026-05-01",
) -> InsightEvidence:
    return InsightEvidence(
        sources=["trend.replacement_rate"],
        evidence_weeks=completed,
        completed_strategies=completed,
        positive_events=10,
        replacement_events=4,
        decision_outcomes=6,
        coverage=EvidenceCoverage(
            status=status,
            available_since=available_since,
            oldest_plan_date=oldest,
            newest_plan_date="2026-07-13",
        ),
        limitations=limitations or [],
    )


def test_complete_coverage_produces_proof_with_count():
    transparency = build_insight_transparency(_insight(), _evidence(completed=8))
    assert transparency.title == TRANSPARENCY_TITLE
    assert transparency.proof_text == "Основано на последних 8 завершённых планах."
    assert transparency.coverage_text == COVERAGE_TEXTS["complete"]
    assert transparency.availability_text is None
    assert transparency.limitations_text == []


def test_insufficient_coverage_hides_count_and_says_collecting():
    transparency = build_insight_transparency(
        _insight(), _evidence(status="insufficient", completed=1)
    )
    assert transparency.proof_text == PROOF_COLLECTING_TEXT
    assert transparency.coverage_text == COVERAGE_TEXTS["insufficient"]


def test_partial_coverage_maps_limitations_to_fixed_texts():
    transparency = build_insight_transparency(
        _insight(),
        _evidence(
            status="partial",
            completed=4,
            limitations=["not_enough_completed_plans", "legacy_strategies"],
        ),
    )
    assert transparency.coverage_text == COVERAGE_TEXTS["partial"]
    assert transparency.limitations_text == [
        LIMITATION_TEXTS["not_enough_completed_plans"],
        LIMITATION_TEXTS["legacy_strategies"],
    ]


def test_availability_text_only_when_data_starts_later_than_history():
    limited = build_insight_transparency(
        _insight(),
        _evidence(available_since="2026-06-15", oldest="2026-05-01"),
    )
    assert limited.availability_text == AVAILABILITY_LIMITED_TEXT

    aligned = build_insight_transparency(
        _insight(),
        _evidence(available_since="2026-05-01", oldest="2026-05-01"),
    )
    assert aligned.availability_text is None

    unknown = build_insight_transparency(
        _insight(),
        _evidence(available_since=None, oldest="2026-05-01"),
    )
    assert unknown.availability_text is None


def test_all_texts_come_from_the_allowlist():
    allowed = (
        {TRANSPARENCY_TITLE, PROOF_COLLECTING_TEXT, AVAILABILITY_LIMITED_TEXT}
        | set(COVERAGE_TEXTS.values())
        | set(LIMITATION_TEXTS.values())
    )
    proof_pattern = re.compile(
        r"^Основано на последних \d+ завершённых план(е|ах)\.$"
    )
    for status, completed in (("complete", 8), ("partial", 3), ("insufficient", 1)):
        transparency = build_insight_transparency(
            _insight(),
            _evidence(
                status=status,
                completed=completed,
                limitations=list(LIMITATION_TEXTS),
            ),
        )
        texts = [
            transparency.title,
            transparency.proof_text,
            transparency.coverage_text,
            *transparency.limitations_text,
        ]
        if transparency.availability_text is not None:
            texts.append(transparency.availability_text)
        for text in texts:
            assert text in allowed or proof_pattern.match(text), text


def test_texts_never_leak_identifiers():
    transparency = build_insight_transparency(
        _insight(), _evidence(limitations=list(LIMITATION_TEXTS))
    )
    blob = " ".join(
        [
            transparency.title,
            transparency.proof_text,
            transparency.coverage_text,
            *transparency.limitations_text,
        ]
    ).lower()
    for forbidden in ("strategy_", "menu_plan_", "event_", "user_id", "id="):
        assert forbidden not in blob
