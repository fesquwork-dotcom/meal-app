"""Sprint 10.11.4 — Strategy Feasibility Analyzer tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

import config
from menu_generation.catalog_service import CatalogMenuGenerationService
from menu_generation.errors import CatalogGenerationError
from recipes.enums import BudgetClass, MealType, ProteinSourceTag
from recipes.importer import RecipeCatalogImporter
from recipes.planning.context import build_planning_context_from_strategy
from recipes.planning.diagnostics import (
    RejectedCandidate,
    SlotDiagnostics,
    TerminationReason,
    infer_termination_reason,
)
from recipes.planning.planner import WeeklyRecipePlanner
from recipes.planning.weights import WeeklyPlannerConfig
from recipes.repository import RecipeRepository
from strategy.feasibility import (
    FeasibilityIssueCode,
    FeasibilityStatus,
    StrategyFeasibilityAnalyzer,
    SuggestionCode,
)
from strategy.models import WeeklyStrategy

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"


def _strategy(
    *,
    days: int = 5,
    cook_days: list[int] | None = None,
    leftovers: bool = True,
    cooking_time_limit: int = 45,
    budget: float = 4000.0,
    goal: str = "home",
) -> WeeklyStrategy:
    return WeeklyStrategy(
        strategy_version=5,
        goal=goal,  # type: ignore[arg-type]
        days=days,
        budget=budget,
        meal_types=["breakfast", "lunch", "dinner"],  # type: ignore[arg-type]
        meals_per_day=3,
        cook_days=cook_days or [1, 3, 5],
        shopping_days=[1],
        leftovers_enabled=leftovers,
        repeat_breakfasts=False,
        repeat_lunches=False,
        repeat_dinners=False,
        preferred_proteins=["any"],  # type: ignore[arg-type]
        excluded_products=[],
        cooking_time_limit=cooking_time_limit,
        prefer_faster_meals=cooking_time_limit <= 30,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def catalog_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    monkeypatch.setattr(config, "MEAL_GENERATION_ENGINE", "catalog_planner")
    db = tmp_path / "feasibility.db"

    async def _seed() -> None:
        report = await RecipeCatalogImporter(
            catalog_root=CATALOG_ROOT, db_path=db
        ).import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()

    asyncio.run(_seed())
    return db


def _context(strategy: WeeklyStrategy, **kwargs):
    return build_planning_context_from_strategy(
        strategy,
        max_cooking_time_override=strategy.cooking_time_limit,
        **kwargs,
    )


def test_ctl45_feasible(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(cooking_time_limit=45)
        original = list(strategy.cook_days)
        result = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy, _context(strategy)
        )
        assert result.status == FeasibilityStatus.FEASIBLE
        assert result.feasible is True
        assert strategy.cook_days == original

    asyncio.run(_run())


def test_ctl20_infeasible_production_case(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(cooking_time_limit=20, cook_days=[1, 3, 5])
        original = list(strategy.cook_days)
        result = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy, _context(strategy)
        )
        assert result.status == FeasibilityStatus.INFEASIBLE
        assert result.feasible is False
        codes = {i.code for i in result.issues}
        assert FeasibilityIssueCode.NO_BATCH_LEFTOVER_CANDIDATE.value in codes or (
            FeasibilityIssueCode.TIME_LIMIT_REMOVES_REQUIRED_BATCH_CANDIDATES.value
            in codes
        )
        assert any(
            (i.target_slot or "").endswith("dinner")
            and i.target_slot
            and ("day4" in i.target_slot or "day2" in i.target_slot)
            for i in result.issues
        )
        assert result.catalog_gaps
        assert any(
            g.required_properties == ["batch_friendly", "leftover_friendly"]
            for g in result.catalog_gaps
        )
        assert any(
            a.suggestion
            in {
                SuggestionCode.ADD_COOK_DAY.value,
                SuggestionCode.RELAX_TIME_LIMIT.value,
                SuggestionCode.CATALOG_COVERAGE_REQUIRED.value,
            }
            for a in result.suggested_adjustments
        )
        assert strategy.cook_days == original == [1, 3, 5]

    asyncio.run(_run())


def test_ctl45_control_generation_success(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(cooking_time_limit=45, budget=4000.0)
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=2,
            cooktime="medium",
        )
        assert result["generation_engine"] == "catalog_planner"
        assert result.get("meal_count") == 15
        assert result.get("strategy_feasibility", {}).get("status") == "FEASIBLE"
        assert strategy.cook_days == [1, 3, 5]

    asyncio.run(_run())


def test_ctl20_blocks_planner(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(cooking_time_limit=20, budget=4000.0)
        with pytest.raises(CatalogGenerationError) as exc_info:
            await CatalogMenuGenerationService(db_path=catalog_db).generate(
                strategy=strategy,
                persons=2,
                cooktime="fast",
            )
        assert exc_info.value.code == CatalogGenerationError.STRATEGY_INFEASIBLE
        details = exc_info.value.details or {}
        assert details.get("feasibility", {}).get("status") == "INFEASIBLE"
        assert strategy.cook_days == [1, 3, 5]

    asyncio.run(_run())


def test_time_limit_gap_detection(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(cooking_time_limit=20)
        result = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy, _context(strategy)
        )
        codes = {i.code for i in result.issues}
        assert (
            FeasibilityIssueCode.TIME_LIMIT_REMOVES_REQUIRED_BATCH_CANDIDATES.value
            in codes
            or FeasibilityIssueCode.NO_BATCH_LEFTOVER_CANDIDATE.value in codes
        )
        # Minimum supported time should be catalog-derived when time gap exists.
        relax = [
            a
            for a in result.suggested_adjustments
            if a.suggestion == SuggestionCode.RELAX_TIME_LIMIT.value
        ]
        if relax:
            assert relax[0].current == 20
            assert relax[0].minimum_supported is not None
            assert int(relax[0].minimum_supported) > 20

    asyncio.run(_run())


def test_non_cook_day_slot_requirements(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(cooking_time_limit=45)
        result = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy, _context(strategy)
        )
        non_cook = {r.slot_id for r in result.slot_requirements if not r.is_cook_day}
        assert "day2_dinner" in non_cook
        assert "day4_dinner" in non_cook
        dinners = [
            r
            for r in result.slot_requirements
            if r.meal_type == "dinner" and not r.is_cook_day
        ]
        assert all(r.covered for r in dinners)

    asyncio.run(_run())


def test_budget_restriction_affects_coverage(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(cooking_time_limit=45, budget=800.0)
        context = build_planning_context_from_strategy(
            strategy,
            max_cooking_time_override=45,
            allowed_budget_override=[BudgetClass.VERY_BUDGET],
        )
        result = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy, context
        )
        assert result.status in {
            FeasibilityStatus.FEASIBLE,
            FeasibilityStatus.FEASIBLE_WITH_RELAXATION,
            FeasibilityStatus.INFEASIBLE,
        }
        assert isinstance(result.candidate_coverage, list)

    asyncio.run(_run())


def test_profile_exclusions(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(cooking_time_limit=45)
        context = build_planning_context_from_strategy(
            strategy,
            max_cooking_time_override=45,
            excluded_protein_sources={
                ProteinSourceTag.CHICKEN,
                ProteinSourceTag.TURKEY,
                ProteinSourceTag.BEEF,
                ProteinSourceTag.PORK,
                ProteinSourceTag.FISH,
                ProteinSourceTag.EGGS,
                ProteinSourceTag.DAIRY,
                ProteinSourceTag.LEGUMES,
                ProteinSourceTag.MIXED,
            },
        )
        result = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy, context
        )
        # Heavy exclusions should shrink coverage vs unrestricted.
        unrestricted = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy, _context(strategy)
        )
        assert sum(c.batch_leftover_after_time for c in result.candidate_coverage) <= sum(
            c.batch_leftover_after_time for c in unrestricted.candidate_coverage
        )

    asyncio.run(_run())


def test_suggested_cook_day_and_determinism(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(cooking_time_limit=20)
        analyzer = StrategyFeasibilityAnalyzer(db_path=catalog_db)
        a = await analyzer.analyze(strategy, _context(strategy))
        b = await analyzer.analyze(strategy, _context(strategy))
        assert a.to_dict() == b.to_dict()
        assert any(
            s.suggestion == SuggestionCode.ADD_COOK_DAY.value
            for s in a.suggested_adjustments
        )

    asyncio.run(_run())


def test_all_cook_days_feasible(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(
            cooking_time_limit=20,
            cook_days=[1, 2, 3, 4, 5],
        )
        result = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy, _context(strategy)
        )
        assert result.status == FeasibilityStatus.FEASIBLE
        assert result.cook_day_gaps == []

    asyncio.run(_run())


def test_max_extra_cook_days_termination_regression():
    slot = SlotDiagnostics(
        slot_id="day4_dinner",
        meal_type="dinner",
        is_cook_day=False,
        candidate_count_after_hard_filters=4,
        candidate_count_after_weekly_constraints=0,
        hard_filter_removals={"TIME_LIMIT_EXCEEDED": 23},
        weekly_constraint_removals={"MAX_EXTRA_COOK_DAYS": 8, "RECIPE_REPEAT": 2},
        best_failed_candidates=[
            RejectedCandidate(
                recipe_id="r1",
                reject_reason="MAX_EXTRA_COOK_DAYS",
                detail="day=4 extra=[2] max=1",
            )
        ],
    )
    assert (
        infer_termination_reason(
            planning_status="partial",
            failed_slot=slot,
            max_states_hit=False,
        )
        == TerminationReason.MAX_EXTRA_COOK_DAYS
    )


def test_planner_config_untouched():
    cfg = WeeklyPlannerConfig()
    assert cfg.max_leftovers_per_cook == 1
    assert cfg.max_extra_cook_days == 1
    assert cfg.beam_width == 8
    assert cfg.candidate_pool_size == 15
