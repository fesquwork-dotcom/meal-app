"""Pure Insight Engine: determinism, fixed ordering, and isolation."""

from __future__ import annotations

import pathlib

from insights.engine import build_insight_summary
from trends.confidence import build_confidence
from trends.models import METRIC_AVAILABILITY, TrendMetric, TrendSummary
from trends.presentation import METRIC_SOURCES, METRIC_TITLES, summary_text


def _metric(metric_id, status="insufficient_data", confidence="insufficient_data"):
    conf = build_confidence(
        evidence_weeks=6 if confidence == "established" else 0,
        completed_strategies=6,
    )
    return TrendMetric(
        id=metric_id,
        title=METRIC_TITLES[metric_id],
        status=status,
        value=None,
        change=None,
        evidence_weeks=conf.weeks,
        confidence=conf,
        source=METRIC_SOURCES[metric_id],
        available_since=METRIC_AVAILABILITY[metric_id],
        summary_text=summary_text(metric_id, status, conf.status),
    )


def _trends() -> TrendSummary:
    return TrendSummary(
        generated_at="2026-07-15T12:00:00+00:00",
        confidence=build_confidence(evidence_weeks=0, completed_strategies=0),
        metrics=[
            _metric("replacement_rate"),
            _metric("positive_completion"),
            _metric("decision_health"),
            _metric("recommendation_effectiveness"),
            _metric("preference_stability"),
        ],
    )


def test_engine_is_deterministic_and_ordered():
    first = build_insight_summary(
        _trends(), None, [], generated_at="2026-07-15T12:00:00+00:00"
    )
    second = build_insight_summary(
        _trends(), None, [], generated_at="2026-07-15T12:00:00+00:00"
    )
    assert first.model_dump() == second.model_dump()
    assert [item.id for item in first.insights] == [
        "replacement_health",
        "replacement_cost",
        "preference_stability",
        "recommendation_effectiveness",
        "positive_completion",
    ]


def test_empty_evidence_produces_only_insufficient_data():
    summary = build_insight_summary(
        _trends(), None, [], generated_at="2026-07-15T12:00:00+00:00"
    )
    assert all(item.status == "insufficient_data" for item in summary.insights)
    assert all(item.confidence.level == "low" for item in summary.insights)


def test_anti_hallucination_phrases_are_absent():
    summary = build_insight_summary(
        _trends(), None, [], generated_at="2026-07-15T12:00:00+00:00"
    )
    payload = summary.model_dump_json().lower()
    for forbidden in (
        "питаться лучше",
        "похудели",
        "стали здоровее",
        "экономите деньги",
    ):
        assert forbidden not in payload


def test_insight_engine_is_pure_and_read_only():
    package_dir = pathlib.Path(__file__).resolve().parents[1] / "insights"
    assert not (package_dir / "repository.py").exists()
    for module in (
        "models.py",
        "engine.py",
        "rules.py",
        "presentation.py",
        "evidence.py",
        "evidence_models.py",
        "transparency.py",
    ):
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


def test_core_layers_do_not_import_insights():
    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    for package in ("decision", "learning", "strategy", "trends", "plan_delta"):
        for path in (backend_dir / package).glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "from insights" not in source, f"{path} must not depend on insights"
            assert "import insights" not in source, f"{path} must not depend on insights"

