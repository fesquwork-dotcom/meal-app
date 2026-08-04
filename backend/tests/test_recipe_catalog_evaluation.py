"""Sprint 10.6 — Catalog evaluation & gap analysis."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from recipes.enums import GoalType, MealType
from recipes.evaluation.engine import CatalogEvaluator, _coverage_ratio, _status
from recipes.evaluation.gap_analyzer import CatalogGapAnalyzer
from recipes.evaluation.loader import ScenarioLoadError, load_evaluation_scenarios
from recipes.evaluation.models import (
    EvaluationScenario,
    ScenarioCoverageStatus,
    ScenarioGroup,
)
from recipes.evaluation.recommendations import build_recommendations
from recipes.evaluation.report_format import format_console_report, format_markdown_report
from recipes.importer import RecipeCatalogImporter
from recipes.selection.context import CandidateSelectionContext

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"
EVAL_DIR = CATALOG_ROOT / "evaluation"


@pytest.fixture
def catalog_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENVIRONMENT", "test")
    import config

    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    db = tmp_path / "eval.db"

    async def _seed() -> None:
        report = await RecipeCatalogImporter(
            catalog_root=CATALOG_ROOT, db_path=db
        ).import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()

    asyncio.run(_seed())
    return db


def test_load_scenarios_ok_and_count():
    scenarios = load_evaluation_scenarios(EVAL_DIR)
    assert len(scenarios) >= 50
    groups = {s.scenario_group for s in scenarios}
    assert ScenarioGroup.BASELINE in groups
    assert ScenarioGroup.GOAL in groups
    assert ScenarioGroup.COMBINED in groups
    assert ScenarioGroup.STRESS in groups
    meals = {s.context.meal_type for s in scenarios}
    assert meals >= {MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER}
    goals = {s.context.goal for s in scenarios if s.context.goal}
    assert set(GoalType) <= goals


def test_duplicate_scenario_id_rejected(tmp_path: Path):
    path = tmp_path / "bad_scenarios.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "scenarios": [
                    {
                        "id": "dup",
                        "name": "a",
                        "scenario_group": "baseline",
                        "expected_min_candidates": 1,
                        "context": {"meal_type": "breakfast", "limit": 5},
                    },
                    {
                        "id": "dup",
                        "name": "b",
                        "scenario_group": "baseline",
                        "expected_min_candidates": 1,
                        "context": {"meal_type": "lunch", "limit": 5},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ScenarioLoadError):
        load_evaluation_scenarios(scenario_file=path)


def test_unknown_enum_and_invalid_weight():
    with pytest.raises(ValidationError):
        EvaluationScenario.model_validate(
            {
                "id": "x",
                "name": "x",
                "scenario_group": "not_a_group",
                "expected_min_candidates": 1,
                "context": {"meal_type": "breakfast"},
            }
        )
    with pytest.raises(ValidationError):
        EvaluationScenario.model_validate(
            {
                "id": "x",
                "name": "x",
                "scenario_group": "baseline",
                "expected_min_candidates": 1,
                "weight": 0,
                "context": {"meal_type": "breakfast"},
            }
        )


def test_disabled_scenario_skipped(tmp_path: Path):
    path = tmp_path / "dis_scenarios.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "scenarios": [
                    {
                        "id": "on",
                        "name": "on",
                        "scenario_group": "baseline",
                        "expected_min_candidates": 1,
                        "enabled": True,
                        "context": {"meal_type": "breakfast", "limit": 5},
                    },
                    {
                        "id": "off",
                        "name": "off",
                        "scenario_group": "baseline",
                        "expected_min_candidates": 1,
                        "enabled": False,
                        "context": {"meal_type": "lunch", "limit": 5},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    loaded = load_evaluation_scenarios(scenario_file=path)
    assert [s.id for s in loaded] == ["on"]


def test_coverage_status_helpers():
    assert _status(5, 5) == ScenarioCoverageStatus.COVERED
    assert _status(3, 5) == ScenarioCoverageStatus.WEAK
    assert _status(0, 5) == ScenarioCoverageStatus.CRITICAL
    assert _status(0, 0) == ScenarioCoverageStatus.EXPECTED_EMPTY
    assert _coverage_ratio(4, 5) == 0.8
    assert _coverage_ratio(10, 5) == 1.0
    assert _coverage_ratio(0, 0) == 1.0


def test_baseline_regression(catalog_db: Path):
    async def _run() -> None:
        evaluator = CatalogEvaluator(db_path=catalog_db)
        report = await evaluator.evaluate(group="baseline")
        by_id = {r.scenario_id: r for r in report.scenario_results}
        for meal in ("breakfast", "lunch", "dinner"):
            result = by_id[f"baseline_{meal}"]
            assert result.actual_candidates >= 8
            assert result.status != ScenarioCoverageStatus.CRITICAL

    asyncio.run(_run())


def test_full_evaluation_integration(catalog_db: Path, tmp_path: Path):
    async def _run() -> None:
        evaluator = CatalogEvaluator(db_path=catalog_db)
        report = await evaluator.evaluate()
        assert report.total_scenarios >= 50
        assert report.catalog_recipe_count == 30
        assert report.weak_scenarios >= 1
        assert 0.0 <= report.weighted_coverage_score <= 1.0
        assert "breakfast" in report.coverage_by_meal_type
        assert report.common_filter_failures is not None
        assert report.catalog_gap_clusters
        assert report.recommended_additions

        known = next(
            r
            for r in report.scenario_results
            if r.scenario_id == "dinner_weight_loss_quick_no_fish"
        )
        assert known.status in {
            ScenarioCoverageStatus.WEAK,
            ScenarioCoverageStatus.COVERED,
        }
        if known.status == ScenarioCoverageStatus.WEAK:
            assert known.actual_candidates < known.expected_min_candidates

        # Determinism
        again = await evaluator.evaluate()
        assert [r.scenario_id for r in report.scenario_results] == [
            r.scenario_id for r in again.scenario_results
        ]
        assert [r.coverage_ratio for r in report.scenario_results] == [
            r.coverage_ratio for r in again.scenario_results
        ]

        md = format_markdown_report(report)
        assert "Executive Summary" in md
        console = format_console_report(report, show_critical=True)
        assert "Weighted coverage" in console

        out_json = tmp_path / "coverage.json"
        out_json.write_text(
            json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        assert out_json.exists()
        out_md = tmp_path / "coverage.md"
        out_md.write_text(md, encoding="utf-8")
        assert "Gap Clusters" in out_md.read_text(encoding="utf-8")

    asyncio.run(_run())


def test_gap_analyzer_does_not_merge_different_meals():
    from recipes.evaluation.models import EvaluationScenarioResult

    scenarios = {
        "a": EvaluationScenario.model_validate(
            {
                "id": "a",
                "name": "a",
                "scenario_group": "combined",
                "expected_min_candidates": 5,
                "context": {
                    "meal_type": "dinner",
                    "goal": "weight_loss",
                    "max_total_time_minutes": 30,
                    "limit": 10,
                },
            }
        ),
        "b": EvaluationScenario.model_validate(
            {
                "id": "b",
                "name": "b",
                "scenario_group": "combined",
                "expected_min_candidates": 5,
                "context": {
                    "meal_type": "lunch",
                    "goal": "weight_loss",
                    "max_total_time_minutes": 30,
                    "limit": 10,
                },
            }
        ),
    }
    results = [
        EvaluationScenarioResult(
            scenario_id="a",
            scenario_name="a",
            scenario_group=ScenarioGroup.COMBINED,
            expected_min_candidates=5,
            actual_candidates=2,
            coverage_ratio=0.4,
            status=ScenarioCoverageStatus.WEAK,
            selection_status="insufficient_candidates",
            weight=1.0,
            meal_type="dinner",
            goal="weight_loss",
            max_total_time_minutes=30,
        ),
        EvaluationScenarioResult(
            scenario_id="b",
            scenario_name="b",
            scenario_group=ScenarioGroup.COMBINED,
            expected_min_candidates=5,
            actual_candidates=2,
            coverage_ratio=0.4,
            status=ScenarioCoverageStatus.WEAK,
            selection_status="insufficient_candidates",
            weight=1.0,
            meal_type="lunch",
            goal="weight_loss",
            max_total_time_minutes=30,
        ),
    ]
    clusters = CatalogGapAnalyzer().analyze(results, scenarios)
    assert len(clusters) == 2


def test_cli_evaluate(catalog_db: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    import config

    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    from recipes.cli import main

    out = tmp_path / "COVERAGE_REPORT.md"
    code = main(
        [
            "evaluate",
            "--group",
            "baseline",
            "--db",
            str(catalog_db),
            "--output",
            str(out),
            "--show-critical",
        ]
    )
    assert code == 0
    assert out.exists()
    assert "Coverage by Meal Type" in out.read_text(encoding="utf-8")

    out_json = tmp_path / "c.json"
    code2 = main(
        [
            "evaluate",
            "--group",
            "baseline",
            "--db",
            str(catalog_db),
            "--json",
            "--output",
            str(out_json),
        ]
    )
    assert code2 == 0
    data = json.loads(out_json.read_text(encoding="utf-8"))
    assert data["total_scenarios"] == 3
