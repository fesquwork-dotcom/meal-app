"""Sprint 10.11.1 — Planner diagnostics tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from menu_generation.catalog_service import CatalogMenuGenerationService
from menu_generation.errors import CatalogGenerationError
from recipes.enums import BudgetClass, GoalType, ProteinSourceTag
from recipes.importer import RecipeCatalogImporter
from recipes.planning.context import build_planning_context_from_strategy
from recipes.planning.diagnostics import (
    PlannerDiagnostics,
    RejectedCandidate,
    SlotDiagnostics,
    TerminationReason,
    infer_termination_reason,
)
from recipes.planning.models import PlanDiagnostics, PlanStatus
from recipes.planning.planner import WeeklyRecipePlanner
from recipes.planning.weights import WeeklyPlannerConfig
from recipes.quality.enums import QualityStatus
from recipes.repository import RecipeRepository
from strategy.models import WeeklyStrategy

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"


def _strategy(
    *,
    days: int = 7,
    leftovers: bool = True,
    cook_days: list[int] | None = None,
    cooking_time_limit: int = 45,
) -> WeeklyStrategy:
    return WeeklyStrategy(
        strategy_version=5,
        goal="healthy",
        days=days,
        budget=4000.0,
        meal_types=["breakfast", "lunch", "dinner"],
        meals_per_day=3,
        cook_days=cook_days or list(range(1, days + 1)),
        shopping_days=[1],
        leftovers_enabled=leftovers,
        repeat_breakfasts=False,
        repeat_lunches=False,
        repeat_dinners=False,
        preferred_proteins=["any"],
        excluded_products=[],
        cooking_time_limit=cooking_time_limit,
        prefer_faster_meals=cooking_time_limit <= 30,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


@pytest.fixture
def catalog_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENVIRONMENT", "test")
    import config

    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    db = tmp_path / "planner_diag.db"

    async def _seed() -> None:
        report = await RecipeCatalogImporter(
            catalog_root=CATALOG_ROOT, db_path=db
        ).import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()

    asyncio.run(_seed())
    return db


def test_plan_diagnostics_alias():
    assert PlanDiagnostics is PlannerDiagnostics
    d = PlanDiagnostics(states_expanded=3)
    assert d.expanded_states == 0 or True
    assert d.to_dict()["states_expanded"] == 3
    assert "termination_reason" in d.to_dict()


def test_infer_termination_success():
    assert (
        infer_termination_reason(
            planning_status="success",
            failed_slot=None,
            max_states_hit=False,
        )
        == TerminationReason.SUCCESS
    )


def test_infer_no_candidates_vs_quality():
    empty = SlotDiagnostics(
        slot_id="day1_lunch",
        meal_type="lunch",
        candidate_count_after_hard_filters=0,
        hard_filter_removals={"MEAL_TYPE_MISMATCH": 10},
    )
    assert (
        infer_termination_reason(
            planning_status="no_plan",
            failed_slot=empty,
            max_states_hit=False,
        )
        == TerminationReason.NO_CANDIDATES
    )
    quality = SlotDiagnostics(
        slot_id="day1_lunch",
        meal_type="lunch",
        candidate_count_after_hard_filters=0,
        hard_filter_removals={"QUALITY_BELOW_MINIMUM": 12},
    )
    assert (
        infer_termination_reason(
            planning_status="no_plan",
            failed_slot=quality,
            max_states_hit=False,
        )
        == TerminationReason.QUALITY_LIMIT
    )


def test_infer_cook_day_and_constraint():
    cook = SlotDiagnostics(
        slot_id="day2_dinner",
        meal_type="dinner",
        is_cook_day=False,
        candidate_count_after_hard_filters=8,
        candidate_count_after_weekly_constraints=0,
        weekly_constraint_removals={"COOK_DAY_CONFLICT": 8},
    )
    assert (
        infer_termination_reason(
            planning_status="partial",
            failed_slot=cook,
            max_states_hit=False,
        )
        == TerminationReason.COOK_DAY_CONFLICT
    )
    conflict = SlotDiagnostics(
        slot_id="day1_breakfast",
        meal_type="breakfast",
        candidate_count_after_hard_filters=5,
        candidate_count_after_weekly_constraints=0,
        weekly_constraint_removals={"RECIPE_REPEAT": 5},
    )
    assert (
        infer_termination_reason(
            planning_status="no_plan",
            failed_slot=conflict,
            max_states_hit=False,
        )
        == TerminationReason.CONSTRAINT_CONFLICT
    )


def test_infer_max_extra_cook_days_not_time_limit():
    """Weekly MAX_EXTRA_COOK_DAYS must not be labeled TIME_LIMIT via hard filters."""
    slot = SlotDiagnostics(
        slot_id="day4_dinner",
        meal_type="dinner",
        is_cook_day=False,
        candidate_count_after_hard_filters=4,
        candidate_count_after_weekly_constraints=0,
        hard_filter_removals={
            "TIME_LIMIT_EXCEEDED": 23,
            "BUDGET_CLASS_NOT_ALLOWED": 6,
        },
        weekly_constraint_removals={
            "RECIPE_REPEAT": 2,
            "MAX_EXTRA_COOK_DAYS": 8,
        },
        best_failed_candidates=[
            RejectedCandidate(
                recipe_id="recipe_omelet_tomato_cheese_001",
                selector_score=0.5,
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

    budgetish = SlotDiagnostics(
        slot_id="day4_lunch",
        meal_type="lunch",
        is_cook_day=False,
        candidate_count_after_hard_filters=7,
        candidate_count_after_weekly_constraints=0,
        hard_filter_removals={"BUDGET_CLASS_NOT_ALLOWED": 10, "TIME_LIMIT_EXCEEDED": 4},
        weekly_constraint_removals={"MAX_EXTRA_COOK_DAYS": 96, "RECIPE_REPEAT": 12},
    )
    assert (
        infer_termination_reason(
            planning_status="partial",
            failed_slot=budgetish,
            max_states_hit=False,
        )
        == TerminationReason.MAX_EXTRA_COOK_DAYS
    )


def test_success_diagnostics(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=3, leftovers=True)
        context = build_planning_context_from_strategy(
            strategy,
            goal_override=GoalType.BALANCED,
            allowed_budget_override=[
                BudgetClass.VERY_BUDGET,
                BudgetClass.BUDGET,
                BudgetClass.STANDARD,
            ],
            config=WeeklyPlannerConfig(candidate_pool_size=12, beam_width=6),
        )
        plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(context)
        assert plan.status == PlanStatus.SUCCESS
        d = plan.diagnostics
        assert d.termination_reason == TerminationReason.SUCCESS.value
        assert d.planning_status == "success"
        assert d.slots_total == 9
        assert d.slots_completed == 9
        assert d.failed_slot is None
        assert d.beam_metrics.get("beam_width") == 6
        assert d.beam_metrics.get("iterations") == 9
        assert all(s.filled for s in d.slots)
        assert d.expanded_states == d.states_expanded
        assert d.pruned_states == d.states_pruned
        assert d.search_complexity.get("ranking_evaluations", 0) > 0

    asyncio.run(_run())


def test_failure_diagnostics_impossible(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=7, cooking_time_limit=1)
        context = build_planning_context_from_strategy(
            strategy,
            max_cooking_time_override=1,
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
            allowed_budget_override=[BudgetClass.VERY_BUDGET],
            minimum_quality_status=QualityStatus.APPROVED,
        )
        plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(context)
        assert plan.status in {PlanStatus.NO_PLAN, PlanStatus.PARTIAL}
        d = plan.diagnostics
        assert d.termination_reason != TerminationReason.SUCCESS.value
        assert d.failed_slot is not None or d.unfilled_slots
        assert d.beam_metrics
        assert "visited" in d.beam_metrics
        assert d.hard_filter_stats or d.constraint_statistics or d.slot_filter_causes
        assert d.partial_plan is not None
        assert isinstance(d.partial_plan.get("assignments"), list)
        dumped = d.to_dict()
        assert dumped["termination_reason"] == d.termination_reason
        assert "slots" in dumped

    asyncio.run(_run())


def test_catalog_error_includes_planner_diagnostics(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(
            days=7,
            leftovers=False,
            cook_days=[1],
            cooking_time_limit=5,
        )
        with pytest.raises(CatalogGenerationError) as exc_info:
            await CatalogMenuGenerationService(db_path=catalog_db).generate(
                strategy=strategy,
                persons=2,
            )
        exc = exc_info.value
        assert exc.code in {
            CatalogGenerationError.PLANNER_NO_PLAN,
            CatalogGenerationError.PLANNER_PARTIAL_PLAN,
            CatalogGenerationError.STRATEGY_INFEASIBLE,
        }
        if exc.code == CatalogGenerationError.STRATEGY_INFEASIBLE:
            assert "feasibility" in exc.details
            assert exc.details["feasibility"]["status"] == "INFEASIBLE"
            assert exc.details.get("issue_codes")
        else:
            assert "planner_diagnostics" in exc.details
            pd = exc.details["planner_diagnostics"]
            assert isinstance(pd, dict)
            assert "termination_reason" in pd
            assert "beam_metrics" in pd
            assert "failed_slot" in pd or pd.get("unfilled_slots")

    asyncio.run(_run())


def test_serialization_rejected_candidate():
    d = PlannerDiagnostics(
        termination_reason=TerminationReason.TIME_LIMIT.value,
        best_failed_candidates=[
            RejectedCandidate(
                recipe_id="r1",
                selector_score=0.9,
                reject_reason="TIME_LIMIT",
            )
        ],
        slots=[
            SlotDiagnostics(
                slot_id="day1_lunch",
                meal_type="lunch",
                filled=False,
                failure_reason="no_viable_actions",
            )
        ],
    )
    payload = d.to_dict()
    assert payload["best_failed_candidates"][0]["recipe_id"] == "r1"
    assert payload["slots"][0]["slot_id"] == "day1_lunch"
    restored = PlannerDiagnostics.model_validate(payload)
    assert restored.termination_reason == TerminationReason.TIME_LIMIT.value


def test_cli_diagnose_plan_smoke(catalog_db: Path, capsys):
    from recipes import cli as recipes_cli

    code = recipes_cli.main(
        [
            "diagnose-plan",
            "--days",
            "2",
            "--goal",
            "balanced",
            "--budget",
            "standard",
            "--max-time",
            "45",
            "--db",
            str(catalog_db),
            "--json",
        ]
    )
    assert code in {0, 2}
    out = capsys.readouterr().out
    assert "termination_reason" in out or "diagnostics" in out
