"""Sprint 10.9 — Catalog expansion, planner readiness, diversity, relations."""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest
import yaml

from recipes.diversity_report import run_diversity_report
from recipes.enums import MealType
from recipes.evaluation.engine import CatalogEvaluator
from recipes.evaluation.models import ScenarioCoverageStatus
from recipes.importer import RecipeCatalogImporter
from recipes.planner_readiness import run_planner_readiness
from recipes.quality.enums import CreationMethod
from recipes.quality.audit import RecipeQualityAuditor
from recipes.repository import RecipeRepository

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"
RELATIONS_PATH = CATALOG_ROOT / "relations" / "relations.yaml"
BASELINE_PATH = CATALOG_ROOT / "evaluation" / "BASELINE_SPRINT_10_9.json"

SPRINT_10_9_NEW_IDS = {
    "recipe_spinach_cottage_frittata_001",
    "recipe_eggs_veg_toast_001",
    "recipe_mushroom_egg_scramble_bf_001",
    "recipe_cottage_berries_bowl_001",
    "recipe_savory_cottage_cucumber_001",
    "recipe_yogurt_oats_berries_001",
    "recipe_millet_milk_porridge_001",
    "recipe_couscous_milk_breakfast_001",
    "recipe_overnight_oats_classic_001",
    "recipe_chickpea_hummus_toast_001",
    "recipe_cottage_lavash_roll_bf_001",
    "recipe_baked_oat_apple_001",
    "recipe_egg_veg_rice_bowl_flex_001",
    "recipe_chickpea_yogurt_bowl_flex_001",
    "recipe_turkey_couscous_lunch_001",
    "recipe_chicken_rice_bowl_lunch_001",
    "recipe_chicken_cabbage_skillet_lunch_001",
    "recipe_beef_tomato_pasta_lunch_001",
    "recipe_beef_pepper_rice_lunch_001",
    "recipe_white_fish_couscous_lunch_001",
    "recipe_tuna_rice_bowl_lunch_001",
    "recipe_red_lentil_tomato_quick_001",
    "recipe_chickpea_couscous_lunch_001",
    "recipe_bean_veg_rice_lunch_001",
    "recipe_cottage_veg_lunch_bowl_001",
    "recipe_egg_potato_skillet_lunch_001",
    "recipe_turkey_bean_lunch_001",
    "recipe_pasta_peas_cheese_lunch_001",
    "recipe_turkey_cabbage_dinner_001",
    "recipe_beef_zucchini_dinner_001",
    "recipe_chicken_mushroom_dinner_001",
    "recipe_chickpea_pepper_dinner_001",
    "recipe_bean_spinach_dinner_001",
    "recipe_fish_veg_skillet_dinner_001",
    "recipe_tuna_zucchini_dinner_001",
    "recipe_egg_tomato_skillet_dinner_001",
    "recipe_chicken_peas_carrot_dinner_001",
    "recipe_lentil_veg_dinner_skillet_001",
    "recipe_beef_onion_pepper_dinner_001",
    "recipe_veg_cheese_skillet_dinner_001",
}

SOURCE_REVIEWED_EXISTING = {
    "recipe_buckwheat_milk_001",
    "recipe_fried_eggs_veg_001",
    "recipe_oatmeal_apple_cinnamon_001",
    "recipe_yogurt_oats_banana_001",
    "recipe_pasta_tuna_tomato_001",
    "recipe_stewed_beans_veg_001",
    "recipe_turkey_veg_skillet_001",
    "recipe_chicken_noodle_soup_001",
    "recipe_pasta_chicken_tomato_001",
    "recipe_rice_chicken_veg_001",
}


@pytest.fixture
def catalog_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENVIRONMENT", "test")
    import config

    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    db = tmp_path / "sprint109.db"

    async def _seed() -> None:
        report = await RecipeCatalogImporter(
            catalog_root=CATALOG_ROOT, db_path=db
        ).import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()

    asyncio.run(_seed())
    return db


def test_sprint_10_9_catalog_size_and_new_recipes(catalog_db: Path):
    async def _run() -> None:
        repo = RecipeRepository(catalog_db)
        assert await repo.count_recipes() == 86
        recipes = await repo.list_active()
        ids = {r.id for r in recipes}
        assert SPRINT_10_9_NEW_IDS.issubset(ids)
        assert len(SPRINT_10_9_NEW_IDS) == 40
        breakfast = sum(1 for r in recipes if r.primary_meal_type == MealType.BREAKFAST)
        lunch = sum(1 for r in recipes if r.primary_meal_type == MealType.LUNCH)
        dinner = sum(1 for r in recipes if r.primary_meal_type == MealType.DINNER)
        assert breakfast == 23
        assert lunch == 33
        assert dinner == 30

    asyncio.run(_run())


def test_sprint_10_9_provenance_sources_and_no_approved(catalog_db: Path):
    async def _run() -> None:
        async with aiosqlite.connect(catalog_db) as db:
            cur = await db.execute(
                "SELECT quality_status, COUNT(*) FROM recipe_provenance GROUP BY quality_status"
            )
            dist = {row[0]: row[1] for row in await cur.fetchall()}
            assert dist.get("approved", 0) == 0
            assert "approved" not in dist

            for rid in SPRINT_10_9_NEW_IDS:
                cur = await db.execute(
                    "SELECT creation_method, source_count FROM recipe_provenance WHERE recipe_id=?",
                    (rid,),
                )
                row = await cur.fetchone()
                assert row is not None, rid
                assert row[0] == CreationMethod.SOURCE_ADAPTED.value
                assert row[1] >= 2
                cur = await db.execute(
                    "SELECT COUNT(*) FROM recipe_sources WHERE recipe_id=?",
                    (rid,),
                )
                assert (await cur.fetchone())[0] >= 2

            # Existing seeds: sources attached for review; creation_method stays agent_generated
            for rid in SOURCE_REVIEWED_EXISTING:
                cur = await db.execute(
                    "SELECT creation_method, source_count FROM recipe_provenance WHERE recipe_id=?",
                    (rid,),
                )
                row = await cur.fetchone()
                assert row is not None, rid
                assert row[1] >= 2
                cur = await db.execute(
                    "SELECT COUNT(*) FROM recipe_sources WHERE recipe_id=?",
                    (rid,),
                )
                assert (await cur.fetchone())[0] >= 2

        auditor = RecipeQualityAuditor(db_path=catalog_db)
        report = await auditor.run(mode="apply")
        assert report.recipe_count == 86
        assert report.approved_count == 0
        assert report.source_verified_count >= 50

    asyncio.run(_run())


def test_sprint_10_9_relations_at_least_60_new():
    data = yaml.safe_load(RELATIONS_PATH.read_text(encoding="utf-8"))
    rels = data["relations"]
    assert len(rels) >= 95
    new_ids = [r for r in rels if int(str(r["id"]).split("_", 1)[1]) >= 36]
    assert len(new_ids) >= 60
    touched = set()
    for r in new_ids:
        touched.add(r["source_recipe_id"])
        touched.add(r["target_recipe_id"])
    assert len(touched & SPRINT_10_9_NEW_IDS) >= 30


def test_sprint_10_9_coverage_dinner_quick_no_egg(catalog_db: Path):
    async def _run() -> None:
        baseline = yaml.safe_load(BASELINE_PATH.read_text(encoding="utf-8"))
        assert baseline["recipes"] == 40
        assert baseline["dinner_quick_no_egg"] == "weak_4_of_5"

        evaluator = CatalogEvaluator(db_path=catalog_db)
        report = await evaluator.evaluate()
        assert report.catalog_recipe_count == 86
        by_id = {r.scenario_id: r for r in report.scenario_results}
        assert by_id["dinner_quick_no_egg"].status == ScenarioCoverageStatus.COVERED
        assert report.weighted_coverage_score >= baseline["weighted_coverage"]
        assert report.weak_scenarios <= baseline["weak"]
        assert report.critical_scenarios <= baseline["critical"]

    asyncio.run(_run())


def test_sprint_10_9_planner_readiness_and_diversity(catalog_db: Path, tmp_path: Path):
    async def _run() -> None:
        planner_out = tmp_path / "PLANNER_READINESS_REPORT.md"
        diversity_out = tmp_path / "DIVERSITY_REPORT.md"
        readiness = await run_planner_readiness(db_path=catalog_db, output=planner_out)
        assert readiness.status == "ready_for_v1"
        assert readiness.total_active_recipes == 86
        assert readiness.source_verified >= 50
        assert readiness.relations_count >= 95
        assert planner_out.is_file()

        diversity = await run_diversity_report(db_path=catalog_db, output=diversity_out)
        assert diversity.total_active_recipes == 86
        assert diversity_out.is_file()

    asyncio.run(_run())
