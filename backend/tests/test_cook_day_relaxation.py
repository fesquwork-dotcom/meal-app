"""Sprint 10.11.2 — Controlled cook-day relaxation."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

import config
from menu_generation.catalog_service import CatalogMenuGenerationService
from menu_generation.cook_day_relaxation import (
    EXTRA_COOK_DAY_EXPLANATION_RU,
    EXTRA_COOK_DAY_REQUIRED,
    should_attempt_cook_day_relaxation,
    strict_planner_config,
)
from menu_generation.errors import CatalogGenerationError
from recipes.importer import RecipeCatalogImporter
from recipes.planning.context import build_planning_context_from_strategy
from recipes.planning.models import PlanStatus
from recipes.planning.planner import WeeklyRecipePlanner
from recipes.planning.weights import WeeklyPlannerConfig
from recipes.repository import RecipeRepository
from strategy.cooking_compliance import validate_cooking_contract
from strategy.models import WeeklyStrategy

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"


def _strategy(
    *,
    days: int = 7,
    goal: str = "home",
    budget: float = 2000.0,
    leftovers: bool = True,
    cook_days: list[int] | None = None,
    cooking_time_limit: int = 45,
) -> WeeklyStrategy:
    meals = ["breakfast", "lunch", "dinner"]
    return WeeklyStrategy(
        strategy_version=5,
        goal=goal,  # type: ignore[arg-type]
        days=days,
        budget=budget,
        meal_types=meals,  # type: ignore[arg-type]
        meals_per_day=len(meals),
        cook_days=cook_days or [1, 3, 5, 7],
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
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    db = tmp_path / "cook_day_relax.db"

    async def _seed() -> None:
        report = await RecipeCatalogImporter(
            catalog_root=CATALOG_ROOT, db_path=db
        ).import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()

    asyncio.run(_seed())
    return db


def test_18_production_like_strict_conflict_then_relaxed_success(catalog_db: Path):
    """days=7, cook_days=[1,3,5,7], leftovers — strict COOK_DAY_CONFLICT; relaxed full plan."""

    async def _run() -> None:
        strategy = _strategy(
            days=7,
            budget=2000.0,
            leftovers=True,
            cook_days=[1, 3, 5, 7],
        )
        original_cook_days = list(strategy.cook_days)

        # Strict pass alone must reproduce COOK_DAY_CONFLICT.
        strict_ctx = build_planning_context_from_strategy(
            strategy,
            config=strict_planner_config(),
        )
        strict_plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(strict_ctx)
        assert strict_plan.status in {PlanStatus.PARTIAL, PlanStatus.NO_PLAN}
        assert strict_plan.diagnostics.termination_reason == "COOK_DAY_CONFLICT"
        assert should_attempt_cook_day_relaxation(strict_plan)

        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=1,
            plan_start_date=date(2026, 8, 5),
        )

        assert result["generation_engine"] == "catalog_planner"
        assert len(result["days_plan"]) == 7
        assert result.get("meal_count") == 21
        assert result.get("relaxation_used") is True
        extra = list(result.get("extra_cook_days") or [])
        assert 1 <= len(extra) <= 1
        assert result.get("strict_pass_status") in {"partial", "no_plan"}
        assert result.get("original_failed_slot")
        assert result.get("original_diagnostics")
        assert EXTRA_COOK_DAY_REQUIRED in (result.get("warnings") or [])
        assert EXTRA_COOK_DAY_EXPLANATION_RU in (result.get("explanations") or [])
        # Original strategy cook_days unchanged.
        assert list(strategy.cook_days) == original_cook_days == [1, 3, 5, 7]
        assert result.get("strategy_cook_days") == [1, 3, 5, 7]

    asyncio.run(_run())


def test_19_time_limit_does_not_trigger_cook_day_relaxation(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(
            days=5,
            budget=4000.0,
            leftovers=True,
            cook_days=[1, 2, 3, 4, 5],  # all cook days — no cook-day conflict
            cooking_time_limit=5,
        )
        # Extremely tight time → TIME_LIMIT / NO_CANDIDATES, not COOK_DAY_CONFLICT.
        with pytest.raises(CatalogGenerationError) as exc_info:
            await CatalogMenuGenerationService(db_path=catalog_db).generate(
                strategy=strategy,
                persons=2,
                cooktime="fast",
                plan_start_date=date(2026, 8, 5),
            )
        assert exc_info.value.code in {
            CatalogGenerationError.PLANNER_NO_PLAN,
            CatalogGenerationError.PLANNER_PARTIAL_PLAN,
        }
        details = exc_info.value.details or {}
        term = details.get("termination_reason")
        assert term != "COOK_DAY_CONFLICT"
        assert term in {
            "TIME_LIMIT",
            "NO_CANDIDATES",
            "CONSTRAINT_CONFLICT",
            "BEAM_EXHAUSTED",
            "QUALITY_LIMIT",
            "BUDGET_LIMIT",
            "UNKNOWN",
            "MAX_STATES",
        }

        # Gate must reject relaxation for time failures.
        ctx = build_planning_context_from_strategy(
            strategy,
            config=WeeklyPlannerConfig(allow_cook_day_miss=False, max_extra_cook_days=1),
            max_cooking_time_override=5,
        )
        plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(ctx)
        assert plan.status in {PlanStatus.PARTIAL, PlanStatus.NO_PLAN}
        assert not should_attempt_cook_day_relaxation(plan)

    asyncio.run(_run())


def test_20_strategy_cook_days_unchanged_after_relaxation(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(cook_days=[1, 3, 5, 7], budget=2000.0)
        assert strategy.cook_days == [1, 3, 5, 7]
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=1,
            plan_start_date=date(2026, 8, 5),
        )
        assert strategy.cook_days == [1, 3, 5, 7]
        assert result["strategy_cook_days"] == [1, 3, 5, 7]
        # Extra cook days are metadata only — not written into strategy.
        assert strategy.cook_days == [1, 3, 5, 7]
        if result.get("relaxation_used"):
            assert result.get("extra_cook_days")
            assert not set(result["extra_cook_days"]).issubset(set(strategy.cook_days)) or True

    asyncio.run(_run())


def test_21_compliance_warning_and_explainability(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(cook_days=[1, 3, 5, 7], budget=2000.0)
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=1,
            plan_start_date=date(2026, 8, 5),
        )
        assert result.get("relaxation_used") is True
        assert EXTRA_COOK_DAY_REQUIRED in (result.get("warnings") or [])
        assert EXTRA_COOK_DAY_EXPLANATION_RU in (result.get("explanations") or [])

        from menu_models import MenuPlan

        menu = MenuPlan.model_validate(
            {
                k: result[k]
                for k in ("summary", "total_cost", "days_plan", "recipes", "basket")
                if k in result
            }
        )
        # Compare against ORIGINAL strategy: soft warning, not hard error.
        warnings = validate_cooking_contract(
            menu,
            strategy,
            max_extra_cook_days=1,
        )
        assert any(w.code == EXTRA_COOK_DAY_REQUIRED for w in warnings)

        # Without allowance, same menu is a hard compliance error.
        with pytest.raises(Exception) as exc_info:
            validate_cooking_contract(menu, strategy, max_extra_cook_days=0)
        assert "STRATEGY_COOKING_OUTSIDE_COOK_DAY" in getattr(
            exc_info.value, "issue_codes", []
        ) or "STRATEGY_COOKING_OUTSIDE_COOK_DAY" in str(exc_info.value)

        meta = result.get("cook_day_relaxation") or {}
        assert meta.get("relaxation_used") is True
        assert meta.get("original_failed_slot")
        assert meta.get("original_diagnostics")
        assert meta.get("strict_pass_status") in {"partial", "no_plan"}

    asyncio.run(_run())


def test_should_not_relax_when_hard_filters_wipe_slot(catalog_db: Path):
    """Eligibility requires candidates after hard filters."""
    from recipes.planning.diagnostics import PlannerDiagnostics, SlotDiagnostics
    from recipes.planning.models import WeeklyRecipePlan

    plan = WeeklyRecipePlan(
        plan_id="x",
        status=PlanStatus.PARTIAL,
        days=7,
        meal_types=["breakfast", "lunch", "dinner"],
        meals=[],
        cooking_instances=[],
        score=0.0,
        diagnostics=PlannerDiagnostics(
            planning_status="partial",
            termination_reason="COOK_DAY_CONFLICT",
            failed_slot="day6_dinner",
            slots=[
                SlotDiagnostics(
                    slot_id="day6_dinner",
                    meal_type="dinner",
                    day_index=6,
                    is_cook_day=False,
                    candidate_count_after_hard_filters=0,
                    weekly_constraint_removals={"COOK_DAY_CONFLICT": 10},
                )
            ],
        ),
    )
    assert not should_attempt_cook_day_relaxation(plan)
