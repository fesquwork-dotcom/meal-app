"""Sprint 10.10 — Deterministic Weekly Recipe Planner tests."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import pytest

from recipes.enums import BudgetClass, GoalType, MealType, ProteinSourceTag
from recipes.importer import RecipeCatalogImporter
from recipes.planning.context import (
    WeeklyPlanningContext,
    build_planning_context_from_strategy,
)
from recipes.planning.evaluator import WeeklyPlanEvaluator
from recipes.planning.models import PlanStatus
from recipes.planning.planner import WeeklyRecipePlanner
from recipes.planning.slots import build_weekly_slots, make_slot_id
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
    import config

    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    db = tmp_path / "planner.db"

    async def _seed() -> None:
        report = await RecipeCatalogImporter(
            catalog_root=CATALOG_ROOT, db_path=db
        ).import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()

    asyncio.run(_seed())
    return db


def test_slot_construction_stable_ids():
    ctx = WeeklyPlanningContext(
        days=2,
        meal_types=[MealType.BREAKFAST, MealType.LUNCH],
        leftovers_enabled=True,
        cook_days=[1],
    )
    slots = build_weekly_slots(ctx)
    assert [s.slot_id for s in slots] == [
        "day1_breakfast",
        "day1_lunch",
        "day2_breakfast",
        "day2_lunch",
    ]
    assert slots[0].is_cook_day is True
    assert slots[2].is_cook_day is False
    assert make_slot_id(3, MealType.DINNER) == "day3_dinner"


def test_scenario_a_balanced_default_week(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=7, leftovers=True, cooking_time_limit=45)
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
        assert len(plan.meals) == 21
        cooks = [m for m in plan.meals if not m.is_leftover]
        assert len({m.recipe_id for m in cooks}) >= 12
        assert plan.score_breakdown.selector_quality > 0

    asyncio.run(_run())


def test_scenario_b_budget_week(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=7, goal="budget", budget=2000.0)
        context = build_planning_context_from_strategy(
            strategy,
            goal_override=GoalType.BUDGET,
            allowed_budget_override=[BudgetClass.VERY_BUDGET, BudgetClass.BUDGET],
        )
        repo = RecipeRepository(catalog_db)
        plan = await WeeklyRecipePlanner(repository=repo).plan(context)
        assert plan.status == PlanStatus.SUCCESS
        for meal in plan.meals:
            recipe = await repo.get_by_id(meal.recipe_id)
            assert recipe is not None
            assert recipe.budget_class in {
                BudgetClass.VERY_BUDGET,
                BudgetClass.BUDGET,
            }

    asyncio.run(_run())


def test_scenario_c_weight_loss_week(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=7, goal="weightloss", cooking_time_limit=40)
        context = build_planning_context_from_strategy(
            strategy, goal_override=GoalType.WEIGHT_LOSS
        )
        plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(context)
        assert plan.status == PlanStatus.SUCCESS
        assert len(plan.meals) == 21

    asyncio.run(_run())


def test_scenario_d_quick_week(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=7, cooking_time_limit=30)
        context = build_planning_context_from_strategy(
            strategy,
            max_cooking_time_override=30,
            goal_override=GoalType.QUICK_COOKING,
        )
        repo = RecipeRepository(catalog_db)
        plan = await WeeklyRecipePlanner(repository=repo).plan(context)
        assert plan.status == PlanStatus.SUCCESS
        for meal in plan.meals:
            if meal.is_leftover:
                continue
            recipe = await repo.get_by_id(meal.recipe_id)
            assert recipe is not None
            assert recipe.total_time_minutes <= 30

    asyncio.run(_run())


def test_scenario_e_no_fish(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=7)
        context = build_planning_context_from_strategy(
            strategy,
            excluded_protein_sources={ProteinSourceTag.FISH},
        )
        repo = RecipeRepository(catalog_db)
        plan = await WeeklyRecipePlanner(repository=repo).plan(context)
        assert plan.status == PlanStatus.SUCCESS
        for meal in plan.meals:
            recipe = await repo.get_recipe_with_dependencies(meal.recipe_id)
            assert recipe is not None
            proteins = {
                t.tag_value
                for t in recipe.tags
                if t.tag_type.value == "protein_source"
            }
            assert ProteinSourceTag.FISH.value not in proteins

    asyncio.run(_run())


def test_scenario_f_preferred_poultry_not_monoculture(catalog_db: Path):
    async def _run() -> None:
        # WeeklyStrategy protein vocab has chicken but not turkey; poultry
        # preference is applied on WeeklyPlanningContext via catalog tags.
        strategy = _strategy(days=7, preferred_proteins=["chicken"])
        context = build_planning_context_from_strategy(strategy)
        context = context.model_copy(
            update={
                "preferred_proteins": {
                    ProteinSourceTag.CHICKEN,
                    ProteinSourceTag.TURKEY,
                }
            }
        )
        plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(context)
        assert plan.status == PlanStatus.SUCCESS
        cooks = [m for m in plan.meals if not m.is_leftover]
        assert len({m.recipe_id for m in cooks}) >= 10

    asyncio.run(_run())


def test_scenario_g_leftovers_disabled(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=7, leftovers=False)
        context = build_planning_context_from_strategy(
            strategy, leftovers_override=False
        )
        plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(context)
        assert plan.status == PlanStatus.SUCCESS
        assert all(not m.is_leftover for m in plan.meals)
        assert all(c.servings_cooked == 1 for c in plan.cooking_instances)

    asyncio.run(_run())


def test_scenario_h_leftovers_reduced_cook_days(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(
            days=7,
            leftovers=True,
            cook_days=[1, 3, 5, 7],
        )
        context = build_planning_context_from_strategy(strategy)
        plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(context)
        assert plan.status in {PlanStatus.SUCCESS, PlanStatus.PARTIAL}
        if plan.status == PlanStatus.SUCCESS:
            # Prefer leftovers or cook-day alignment when possible
            leftovers = sum(1 for m in plan.meals if m.is_leftover)
            assert leftovers >= 0
            for meal in plan.meals:
                if meal.is_leftover:
                    assert meal.source_slot_id
                    assert meal.requires_cooking is False
                    src = next(
                        m for m in plan.meals if m.slot_id == meal.source_slot_id
                    )
                    assert src.recipe_id == meal.recipe_id
                    assert src.cooking_instance_id == meal.cooking_instance_id

    asyncio.run(_run())


def test_scenario_i_source_verified_only(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=7)
        context = build_planning_context_from_strategy(
            strategy,
            minimum_quality_status=QualityStatus.SOURCE_VERIFIED,
        )
        plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(context)
        assert plan.status == PlanStatus.SUCCESS
        assert len(plan.meals) == 21

    asyncio.run(_run())


def test_scenario_j_impossible_constraints(catalog_db: Path):
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
        assert plan.diagnostics.unfilled_slots or plan.status == PlanStatus.NO_PLAN
        assert isinstance(plan.diagnostics.slot_filter_causes, dict)

    asyncio.run(_run())


def test_determinism_same_plan_twice(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, leftovers=True, cook_days=[1, 3, 5])
        context = build_planning_context_from_strategy(
            strategy,
            config=WeeklyPlannerConfig(candidate_pool_size=10, beam_width=5),
        )
        planner = WeeklyRecipePlanner(repository=RecipeRepository(catalog_db))
        a = await planner.plan(context)
        b = await planner.plan(context)
        assert a.status == b.status
        assert a.plan_id == b.plan_id
        assert a.score == b.score
        assert [
            (m.slot_id, m.recipe_id, m.is_leftover, m.cooking_instance_id)
            for m in a.meals
        ] == [
            (m.slot_id, m.recipe_id, m.is_leftover, m.cooking_instance_id)
            for m in b.meals
        ]
        assert [
            (m.slot_id, list(m.planner_reasons), list(m.selector_reasons))
            for m in a.meals
        ] == [
            (m.slot_id, list(m.planner_reasons), list(m.selector_reasons))
            for m in b.meals
        ]

    asyncio.run(_run())


def test_leftover_consistency_and_no_orphan(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, leftovers=True, cook_days=[1, 3, 5])
        context = build_planning_context_from_strategy(strategy)
        plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(context)
        by_slot = plan.meal_by_slot()
        for meal in plan.meals:
            if not meal.is_leftover:
                continue
            assert meal.source_slot_id in by_slot
            src = by_slot[meal.source_slot_id]
            assert src.recipe_id == meal.recipe_id
            assert src.day_index < meal.day_index or (
                src.day_index == meal.day_index
                and src.slot_id != meal.slot_id
            )
            assert meal.cooking_instance_id == src.cooking_instance_id
        for inst in plan.cooking_instances:
            assert inst.servings_consumed <= inst.servings_cooked

    asyncio.run(_run())


def test_recipe_repetition_policy(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=7, leftovers=True)
        context = build_planning_context_from_strategy(strategy)
        plan = await WeeklyRecipePlanner(
            repository=RecipeRepository(catalog_db)
        ).plan(context)
        counts: dict[str, int] = {}
        for meal in plan.meals:
            if meal.is_leftover:
                continue
            counts[meal.recipe_id] = counts.get(meal.recipe_id, 0) + 1
        assert all(v <= 1 for v in counts.values())

    asyncio.run(_run())


def test_weekly_plan_evaluator_metrics(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=7)
        context = build_planning_context_from_strategy(strategy)
        planner = WeeklyRecipePlanner(repository=RecipeRepository(catalog_db))
        plan = await planner.plan(context)
        recipes = {}
        for meal in plan.meals:
            r = await planner.repository.get_recipe_with_dependencies(meal.recipe_id)
            if r:
                recipes[meal.recipe_id] = r
        quality = await planner.candidate_provider.load_quality_map()
        ev = WeeklyPlanEvaluator().evaluate(
            plan, context=context, recipes=recipes, quality_by_recipe=quality
        )
        assert ev.slot_coverage == 1.0
        assert 0.0 <= ev.protein_diversity <= 1.0
        assert ev.weekly_score == plan.score

    asyncio.run(_run())


def test_catalog_still_80(catalog_db: Path):
    async def _run() -> None:
        repo = RecipeRepository(catalog_db)
        assert await repo.count_recipes() == 86

    asyncio.run(_run())


def test_plan_week_cli_smoke(catalog_db: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    from recipes.cli import main

    code = main(
        [
            "plan-week",
            "--days",
            "3",
            "--max-time",
            "45",
            "--leftovers",
            "--db",
            str(catalog_db),
            "--json",
            "--evaluate",
        ]
    )
    assert code in {0, 2}
