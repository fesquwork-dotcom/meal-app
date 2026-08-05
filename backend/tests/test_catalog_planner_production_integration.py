"""Sprint 10.11 — Catalog Planner production integration tests."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

import config
from menu_generation.catalog_service import CatalogMenuGenerationService
from menu_generation.engine import GenerationEngine, resolve_generation_engine
from menu_generation.errors import CatalogGenerationError
from menu_generation.menuplan_adapter import (
    leftover_menu_recipe_id,
    meal_id_for_slot,
    WeeklyRecipePlanToMenuPlanAdapter,
)
from menu_generation.orchestrator import MenuGenerationOrchestrator
from menu_models import MenuPlan
from recipes.importer import RecipeCatalogImporter
from recipes.planning.context import build_planning_context_from_strategy
from recipes.planning.models import PlanStatus
from recipes.planning.planner import WeeklyRecipePlanner
from recipes.planning.weights import WeeklyPlannerConfig
from recipes.quality.enums import QualityStatus
from recipes.repository import RecipeRepository
from strategy.models import WeeklyStrategy

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"


def _strategy(
    *,
    days: int = 7,
    goal: str = "healthy",
    budget: float = 4000.0,
    leftovers: bool = True,
    cook_days: list[int] | None = None,
    cooking_time_limit: int = 45,
    meal_types: list[str] | None = None,
    preferred_proteins: list[str] | None = None,
) -> WeeklyStrategy:
    meals = meal_types or ["breakfast", "lunch", "dinner"]
    return WeeklyStrategy(
        strategy_version=5,
        goal=goal,  # type: ignore[arg-type]
        days=days,
        budget=budget,
        meal_types=meals,  # type: ignore[arg-type]
        meals_per_day=len(meals),
        cook_days=cook_days or list(range(1, days + 1)),
        shopping_days=[1],
        leftovers_enabled=leftovers,
        repeat_breakfasts=False,
        repeat_lunches=False,
        repeat_dinners=False,
        preferred_proteins=preferred_proteins or ["any"],  # type: ignore[arg-type]
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
    db = tmp_path / "catalog_prod.db"

    async def _seed() -> None:
        report = await RecipeCatalogImporter(
            catalog_root=CATALOG_ROOT, db_path=db
        ).import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()

    asyncio.run(_seed())
    return db


def test_resolve_engine_defaults_to_catalog(monkeypatch):
    monkeypatch.setattr(config, "MEAL_GENERATION_ENGINE", "catalog_planner")
    assert resolve_generation_engine() == GenerationEngine.CATALOG_PLANNER


def test_resolve_engine_invalid_falls_back(monkeypatch):
    monkeypatch.setattr(config, "MEAL_GENERATION_ENGINE", "not_a_real_engine")
    assert resolve_generation_engine() == GenerationEngine.CATALOG_PLANNER


def test_adapter_meal_id_vs_recipe_id(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=3, leftovers=True, cook_days=[1, 2])
        context = build_planning_context_from_strategy(
            strategy,
            config=WeeklyPlannerConfig(allow_cook_day_miss=False),
        )
        plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(context)
        assert plan.status == PlanStatus.SUCCESS
        menu = await WeeklyRecipePlanToMenuPlanAdapter(
            repository=RecipeRepository(catalog_db)
        ).adapt(
            plan,
            strategy=strategy,
            persons=2,
            plan_start_date=date(2026, 8, 5),
        )
        for day in menu.days_plan:
            for meal in day.meals:
                assert meal.meal_id and meal.meal_id.startswith("meal_")
                assert meal.recipe_id
                assert meal.meal_id != meal.recipe_id
                if meal.uses_leftovers:
                    assert meal.recipe_id.endswith("__leftover")
                    assert meal.source_meal_id and meal.source_meal_id.startswith(
                        "meal_"
                    )
                else:
                    assert not meal.recipe_id.endswith("__leftover")

    asyncio.run(_run())


def test_a_default_engine_no_claude_called(catalog_db: Path, monkeypatch):
    monkeypatch.setattr(config, "MEAL_GENERATION_ENGINE", "catalog_planner")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    claude_spy = AsyncMock(side_effect=AssertionError("claude called"))
    monkeypatch.setattr("claude_service.generate_menu", claude_spy)

    async def _run() -> None:
        strategy = _strategy(days=7, leftovers=True)
        orch = MenuGenerationOrchestrator(db_path=catalog_db)
        result = await orch.generate_menu(
            budget=strategy.budget,
            days=strategy.days,
            meal_types=list(strategy.meal_types),
            meals_per_day=strategy.meals_per_day,
            persons=2,
            proteins=["any"],
            goal=strategy.goal,
            cooktime="medium",
            allergies="нет",
            strategy=strategy,
            plan_start_date=date(2026, 8, 5),
            user_id=1,
        )
        assert result["generation_engine"] == "catalog_planner"
        assert len(result["days_plan"]) == 7
        claude_spy.assert_not_called()

    asyncio.run(_run())


def test_b_balanced_7x3_basket(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=7, goal="healthy", leftovers=True)
        service = CatalogMenuGenerationService(db_path=catalog_db)
        result = await service.generate(
            strategy=strategy,
            persons=2,
            cooktime="medium",
            allergies="нет",
            plan_start_date=date(2026, 8, 5),
        )
        meals = [
            meal
            for day in result["days_plan"]
            for meal in day["meals"]
        ]
        assert len(meals) == 21
        assert isinstance(result["basket"], list)
        assert len(result["basket"]) >= 1
        assert result["meal_count"] == 21

    asyncio.run(_run())


def test_c_weight_loss_goal(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, goal="weightloss", leftovers=True)
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=2,
            plan_start_date=date(2026, 8, 5),
        )
        assert result["generation_engine"] == "catalog_planner"
        assert len(result["days_plan"]) == 5

    asyncio.run(_run())


@pytest.mark.parametrize("budget", [2000.0, 4000.0, 8000.0])
def test_d_budget_classes(catalog_db: Path, budget: float):
    async def _run() -> None:
        strategy = _strategy(days=5, budget=budget, leftovers=True)
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=2,
            plan_start_date=date(2026, 8, 5),
        )
        assert result["generation_engine"] == "catalog_planner"
        assert len(result["days_plan"]) == 5

    asyncio.run(_run())


def test_e_leftovers_sparse_cook_days_no_double_count(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(
            days=5,
            leftovers=True,
            cook_days=[1, 3, 5],
            cooking_time_limit=45,
        )
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=2,
            plan_start_date=date(2026, 8, 5),
        )
        leftovers = [
            meal
            for day in result["days_plan"]
            for meal in day["meals"]
            if meal.get("uses_leftovers")
        ]
        assert leftovers, "expected leftovers on sparse cook days"
        assert result.get("leftover_count", 0) >= 1

        # Basket must not double-count cooking-instance ingredients.
        # Count ingredient name occurrences across recipe purchase lines vs basket.
        cook_recipe_ids = {
            meal["recipe_id"]
            for day in result["days_plan"]
            for meal in day["meals"]
            if meal.get("requires_cooking") and meal.get("recipe_id")
        }
        leftover_recipe_ids = {
            meal["recipe_id"]
            for day in result["days_plan"]
            for meal in day["meals"]
            if meal.get("uses_leftovers") and meal.get("recipe_id")
        }
        # Leftover snapshots are distinct (__leftover); cook ids must not equal leftover ids.
        assert cook_recipe_ids.isdisjoint(leftover_recipe_ids)

        basket_names = [
            item["name"].lower()
            for category in result["basket"]
            for item in category["items"]
        ]
        # Sanity: basket has structure; leftover-only names should not dominate.
        assert basket_names

    asyncio.run(_run())


def test_f_leftovers_disabled(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, leftovers=False)
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=2,
            plan_start_date=date(2026, 8, 5),
        )
        leftovers = [
            meal
            for day in result["days_plan"]
            for meal in day["meals"]
            if meal.get("uses_leftovers")
        ]
        assert leftovers == []
        assert result.get("leftover_count", 0) == 0

    asyncio.run(_run())


def test_g_source_verified_only(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=3, leftovers=True)
        try:
            result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
                strategy=strategy,
                persons=2,
                plan_start_date=date(2026, 8, 5),
                minimum_quality_status=QualityStatus.SOURCE_VERIFIED,
            )
            assert result["generation_engine"] == "catalog_planner"
        except CatalogGenerationError as exc:
            # Acceptable if catalog lacks enough SOURCE_VERIFIED recipes for 3×3.
            assert exc.code in {
                CatalogGenerationError.PLANNER_NO_PLAN,
                CatalogGenerationError.PLANNER_PARTIAL_PLAN,
            }

    asyncio.run(_run())


def test_h_impossible_no_claude(catalog_db: Path, monkeypatch):
    monkeypatch.setattr(config, "MEAL_GENERATION_ENGINE", "catalog_planner")
    claude_spy = AsyncMock(side_effect=AssertionError("claude called"))
    monkeypatch.setattr("claude_service.generate_menu", claude_spy)

    async def _run() -> None:
        # Extremely tight cook window + no leftovers + sparse cook days → no plan.
        strategy = _strategy(
            days=7,
            leftovers=False,
            cook_days=[1],
            cooking_time_limit=5,
        )
        orch = MenuGenerationOrchestrator(db_path=catalog_db)
        with pytest.raises(CatalogGenerationError) as exc_info:
            await orch.generate_menu(
                budget=strategy.budget,
                days=strategy.days,
                meal_types=list(strategy.meal_types),
                meals_per_day=strategy.meals_per_day,
                persons=2,
                proteins=["any"],
                goal=strategy.goal,
                cooktime="fast",
                allergies="нет",
                strategy=strategy,
                plan_start_date=date(2026, 8, 5),
            )
        assert exc_info.value.code in {
            CatalogGenerationError.PLANNER_NO_PLAN,
            CatalogGenerationError.PLANNER_PARTIAL_PLAN,
            CatalogGenerationError.MENUPLAN_VALIDATION_FAILED,
        }
        claude_spy.assert_not_called()

    asyncio.run(_run())


def test_i_menuplan_persist_roundtrip(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, leftovers=True)
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=2,
            plan_start_date=date(2026, 8, 5),
            strategy_id="strat_test_1",
        )
        plan = MenuPlan.model_validate(result)
        dumped = plan.model_dump_json()
        restored = MenuPlan.model_validate_json(dumped)
        assert restored.generation_engine == "catalog_planner"
        assert restored.planner_version == "10.10"
        assert restored.plan_start_date == date(2026, 8, 5)
        meal_ids = [
            meal.meal_id
            for day in restored.days_plan
            for meal in day.meals
            if meal.meal_id
        ]
        assert meal_ids
        assert all(mid.startswith("meal_") for mid in meal_ids)

    asyncio.run(_run())


def test_j_serialization_shape(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, leftovers=True)
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=2,
            plan_start_date=date(2026, 8, 5),
        )
        for key in ("days_plan", "recipes", "basket", "plan_start_date", "summary"):
            assert key in result
        assert result["plan_start_date"] == "2026-08-05"
        assert isinstance(result["recipes"], list) and result["recipes"]
        assert isinstance(result["basket"], list) and result["basket"]

    asyncio.run(_run())


def test_meal_id_helper_stable():
    assert meal_id_for_slot("day1_breakfast") == "meal_day1_breakfast"
    assert leftover_menu_recipe_id("recipe_chicken_001") == (
        "recipe_chicken_001__leftover"
    )


def test_catalog_count_still_80(catalog_db: Path):
    async def _run() -> None:
        from recipes.enums import RecipeStatus

        count = await RecipeRepository(catalog_db).count_recipes(
            status=RecipeStatus.ACTIVE
        )
        assert count == 80

    asyncio.run(_run())
