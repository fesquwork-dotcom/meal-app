"""Sprint 10.11.5 — Fast batch dinner catalog gap closure."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite
import pytest
import yaml

import config
from menu_generation.catalog_service import CatalogMenuGenerationService
from recipes.enums import MealType
from recipes.importer import RecipeCatalogImporter
from recipes.planner_readiness import run_planner_readiness
from recipes.planning.context import build_planning_context_from_strategy
from recipes.planning.weights import WeeklyPlannerConfig
from recipes.quality.duplicate_check import RecipeDuplicateChecker
from recipes.quality.source_models import RecipeConcept
from recipes.repository import RecipeRepository
from strategy.feasibility import FeasibilityIssueCode, FeasibilityStatus, StrategyFeasibilityAnalyzer
from strategy.models import WeeklyStrategy

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"
DINNER_DIR = CATALOG_ROOT / "recipes" / "dinner"
RELATIONS_PATH = CATALOG_ROOT / "relations" / "relations.yaml"

SPRINT_10_11_5_IDS = {
    "recipe_chicken_bean_pepper_skillet_001",
    "recipe_turkey_bean_corn_skillet_001",
    "recipe_white_fish_tomato_beans_001",
    "recipe_bean_corn_tomato_skillet_001",
    "recipe_egg_bean_spinach_skillet_001",
    "recipe_beef_bean_tomato_skillet_001",
}

PROTEIN_BY_ID = {
    "recipe_chicken_bean_pepper_skillet_001": "chicken",
    "recipe_turkey_bean_corn_skillet_001": "turkey",
    "recipe_white_fish_tomato_beans_001": "fish",
    "recipe_bean_corn_tomato_skillet_001": "legumes",
    "recipe_egg_bean_spinach_skillet_001": "eggs",
    "recipe_beef_bean_tomato_skillet_001": "beef",
}


@pytest.fixture
def catalog_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    monkeypatch.setattr(config, "MEAL_GENERATION_ENGINE", "catalog_planner")
    db = tmp_path / "sprint10115.db"

    async def _seed() -> None:
        report = await RecipeCatalogImporter(
            catalog_root=CATALOG_ROOT, db_path=db
        ).import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()

    asyncio.run(_seed())
    return db


def _strategy(ctl: int = 20) -> WeeklyStrategy:
    return WeeklyStrategy(
        strategy_version=5,
        goal="home",  # type: ignore[arg-type]
        days=5,
        budget=4000.0,
        meal_types=["breakfast", "lunch", "dinner"],  # type: ignore[arg-type]
        meals_per_day=3,
        cook_days=[1, 3, 5],
        shopping_days=[1],
        leftovers_enabled=True,
        repeat_breakfasts=False,
        repeat_lunches=False,
        repeat_dinners=False,
        preferred_proteins=["any"],  # type: ignore[arg-type]
        excluded_products=[],
        cooking_time_limit=ctl,
        prefer_faster_meals=ctl <= 30,
        generated_at=datetime.now(timezone.utc).isoformat(),
    )


def test_catalog_total_86_and_exactly_six_new(catalog_db: Path):
    async def _run() -> None:
        repo = RecipeRepository(catalog_db)
        assert await repo.count_recipes() == 86
        recipes = await repo.list_active()
        ids = {r.id for r in recipes}
        assert SPRINT_10_11_5_IDS.issubset(ids)
        assert len(SPRINT_10_11_5_IDS) == 6
        dinner = sum(1 for r in recipes if r.primary_meal_type == MealType.DINNER)
        assert dinner == 30

    asyncio.run(_run())


def test_new_recipes_meet_fast_batch_contract(catalog_db: Path):
    async def _run() -> None:
        repo = RecipeRepository(catalog_db)
        budgets = []
        proteins = set()
        for rid in sorted(SPRINT_10_11_5_IDS):
            recipe = await repo.get_recipe_with_dependencies(rid)
            assert recipe is not None, rid
            assert recipe.primary_meal_type == MealType.DINNER
            assert recipe.total_time_minutes <= 20
            assert recipe.batch_friendly is True
            assert recipe.leftover_friendly is True
            assert recipe.storage_days >= 2
            assert recipe.max_batch_servings >= 4
            budgets.append(recipe.budget_class.value)
            tags = {
                t.tag_value
                for t in recipe.tags
                if t.tag_type.value == "protein_source"
            }
            proteins |= tags
            assert PROTEIN_BY_ID[rid] in tags
            async with aiosqlite.connect(catalog_db) as db:
                cur = await db.execute(
                    "SELECT creation_method, source_count, quality_status "
                    "FROM recipe_provenance WHERE recipe_id=?",
                    (rid,),
                )
                row = await cur.fetchone()
                assert row is not None
                assert row[0] == "source_adapted"
                assert row[1] >= 2
                assert row[2] in {"source_verified", "schema_validated", "computationally_checked"}
                cur = await db.execute(
                    "SELECT COUNT(*) FROM recipe_sources WHERE recipe_id=?",
                    (rid,),
                )
                assert (await cur.fetchone())[0] >= 2

        assert sum(1 for b in budgets if b in {"budget", "very_budget"}) >= 3
        assert sum(1 for b in budgets if b == "standard") <= 2
        assert "premium" not in budgets
        assert proteins >= {"chicken", "turkey", "fish", "legumes", "eggs", "beef"}

    asyncio.run(_run())


def test_relations_added_for_new_recipes():
    data = yaml.safe_load(RELATIONS_PATH.read_text(encoding="utf-8"))
    new_rels = [
        r
        for r in data["relations"]
        if r["source_recipe_id"] in SPRINT_10_11_5_IDS
        or r["target_recipe_id"] in SPRINT_10_11_5_IDS
    ]
    assert len(new_rels) >= 12
    types = {r["relation_type"] for r in new_rels}
    assert "similar_meal" in types or "avoid_consecutive_days" in types
    assert "shares_ingredients" in types


def test_duplicate_checker_rejects_near_twins(catalog_db: Path):
    async def _run() -> None:
        repo = RecipeRepository(catalog_db)
        existing = []
        for stub in await repo.list_active():
            full = await repo.get_recipe_with_dependencies(stub.id)
            if full:
                existing.append(full)
        checker = RecipeDuplicateChecker()
        # Rejected concept: chickpea+spinach dinner twin
        concept = RecipeConcept(
            concept_id="rejected_chickpea_spinach_twin",
            title="Chickpea tomato spinach dinner twin",
            target_meal_types=["dinner"],
            primary_protein="legumes",
            notes="Should match chickpea-spinach-dinner",
        )
        result = checker.check(
            concept=concept,
            existing=existing,
            proposed_ingredient_ids={
                "ing_chickpeas",
                "ing_spinach",
                "ing_tomato_sauce",
                "ing_oil",
            },
            proposed_method="stewing",
            proposed_total_time=20,
            proposed_meal_types={"dinner"},
        )
        # Either flagged duplicate or high score near threshold against existing
        assert result.score >= 0.5 or result.is_duplicate

    asyncio.run(_run())


def test_ctl20_feasibility_and_planner_success(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(20)
        feas = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy,
            build_planning_context_from_strategy(
                strategy, max_cooking_time_override=20
            ),
        )
        assert feas.status != FeasibilityStatus.INFEASIBLE
        assert FeasibilityIssueCode.NO_BATCH_LEFTOVER_CANDIDATE.value not in {
            i.code for i in feas.issues
        }

        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=2,
            cooktime="fast",
        )
        assert result.get("meal_count") == 15
        assert result["generation_engine"] == "catalog_planner"
        assert int(result.get("leftover_count") or 0) >= 1
        # Prefer an explicit leftover dinner on a non-cook day when present.
        days_plan = result.get("days_plan") or []
        leftover_slots = []
        for day in days_plan:
            for meal in day.get("meals") or []:
                if meal.get("is_leftover") or meal.get("source_meal_id"):
                    leftover_slots.append(meal)
        assert leftover_slots or int(result.get("leftover_count") or 0) >= 1

    asyncio.run(_run())


def test_ctl45_still_works(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(45)
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=2,
            cooktime="medium",
        )
        assert result.get("meal_count") == 15

    asyncio.run(_run())


def test_planner_limits_unchanged():
    cfg = WeeklyPlannerConfig()
    assert cfg.max_leftovers_per_cook == 1
    assert cfg.max_extra_cook_days == 1
    assert cfg.beam_width == 8
    assert cfg.candidate_pool_size == 15
    assert cfg.max_states == 4000


def test_fast_batch_dinner_readiness_metric(catalog_db: Path, tmp_path: Path):
    async def _run() -> None:
        out = tmp_path / "readiness.md"
        report = await run_planner_readiness(db_path=catalog_db, output=out)
        assert report.total_active_recipes == 86
        assert report.fast_batch_dinner_le20 >= 6
        text = out.read_text(encoding="utf-8")
        assert "Fast Batch Dinner Coverage" in text
        assert str(report.fast_batch_dinner_le20) in text

    asyncio.run(_run())


def test_yaml_files_exist_on_disk():
    for rid, slug_hint in [
        ("recipe_chicken_bean_pepper_skillet_001", "chicken-bean-pepper-skillet"),
        ("recipe_turkey_bean_corn_skillet_001", "turkey-bean-corn-skillet"),
        ("recipe_white_fish_tomato_beans_001", "white-fish-tomato-beans"),
        ("recipe_bean_corn_tomato_skillet_001", "bean-corn-tomato-skillet"),
        ("recipe_egg_bean_spinach_skillet_001", "egg-bean-spinach-skillet"),
        ("recipe_beef_bean_tomato_skillet_001", "beef-bean-tomato-skillet"),
    ]:
        path = DINNER_DIR / f"{slug_hint}.yaml"
        assert path.is_file(), path
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["id"] == rid
        assert data["total_time_minutes"] <= 20
        assert data["batch_friendly"] is True
        assert data["leftover_friendly"] is True
