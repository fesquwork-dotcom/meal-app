"""Sprint 10.4 — Recipe Catalog foundation tests."""

from __future__ import annotations

import asyncio
import shutil
from decimal import Decimal
from pathlib import Path

import aiosqlite
import pytest
import yaml
from pydantic import ValidationError

from recipes.basket_adapter import (
    merge_normalized_for_test,
    recipe_to_normalized_ingredients,
)
from recipes.catalog_report import build_catalog_report
from recipes.db import ensure_recipe_catalog_tables
from recipes.enums import (
    BudgetClass,
    GoalType,
    MealType,
    RecipeStatus,
    ScalingMode,
)
from recipes.importer import RecipeCatalogImporter, load_catalog_files
from recipes.repository import RecipeRepository
from recipes.scaler import RecipeScaleError, RecipeScaler
from recipes.schemas import RecipeCardSchema, RecipeRelationSchema, RecipeTagSchema
from recipes.validator import RecipeCatalogValidator

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"


@pytest.fixture
def catalog_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENVIRONMENT", "test")
    import config

    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    return tmp_path / "catalog.db"


def test_import_all_30_recipes(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        report = await importer.import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()
        assert report.recipes_written == 30
        assert report.ingredients_written >= 50
        repo = RecipeRepository(catalog_db)
        assert await repo.count_recipes() == 30
        assert await repo.count_recipes(RecipeStatus.ACTIVE) == 30

    asyncio.run(_run())


def test_coverage_meal_types_and_minimums(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        report = await build_catalog_report(db_path=catalog_db, catalog_root=CATALOG_ROOT)
        assert report.total_recipes == 30
        assert report.recipes_by_primary_meal_type.get("breakfast") == 10
        assert report.recipes_by_primary_meal_type.get("lunch") == 10
        assert report.recipes_by_primary_meal_type.get("dinner") == 10
        assert report.quick_recipes >= 4
        assert report.batch_friendly_recipes >= 5
        assert report.leftover_friendly_recipes >= 5
        assert (
            report.recipes_by_budget_class.get("very_budget", 0)
            + report.recipes_by_budget_class.get("budget", 0)
            >= 9
        )
        assert report.relations_count >= 20
        assert not report.validation_errors

    asyncio.run(_run())


def test_dry_run_does_not_write(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        report = await importer.import_catalog(mode="dry_run")
        assert report.ok
        assert report.recipes_written == 0
        async with aiosqlite.connect(catalog_db) as db:
            await ensure_recipe_catalog_tables(db)
            cur = await db.execute("SELECT COUNT(*) AS c FROM recipes")
            row = await cur.fetchone()
            assert row[0] == 0

    asyncio.run(_run())


def test_upsert_idempotent(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="upsert")
        await importer.import_catalog(mode="upsert")
        repo = RecipeRepository(catalog_db)
        assert await repo.count_recipes() == 30

    asyncio.run(_run())


def test_replace_catalog_preserves_user_tables(catalog_db: Path):
    async def _run() -> None:
        async with aiosqlite.connect(catalog_db) as db:
            await db.execute(
                """
                CREATE TABLE IF NOT EXISTS profiles (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT
                )
                """
            )
            await db.execute(
                "INSERT INTO profiles (user_id, first_name) VALUES (42, 'Test')"
            )
            await ensure_recipe_catalog_tables(db)
            await db.execute(
                """
                INSERT INTO recipes (
                    id, slug, name, description, status, version, primary_meal_type,
                    base_servings, yield_weight_g, recommended_portion_min_g,
                    recommended_portion_max_g, scaling_mode, min_batch_servings,
                    max_batch_servings, prep_time_minutes, cook_time_minutes,
                    active_time_minutes, total_time_minutes, difficulty, requires_cooking,
                    batch_friendly, leftover_friendly, storage_days, freezing_supported,
                    budget_class, energy_density, protein_level, fiber_level, satiety_level,
                    calories_per_100g, protein_g_per_100g, fat_g_per_100g, carbs_g_per_100g,
                    image_key, created_at, updated_at
                ) VALUES (
                    'old', 'old', 'Old', 'd', 'active', 1, 'breakfast',
                    1, 100, 80, 120, 'linear', 1, 4, 1, 1, 1, 2, 'easy', 1,
                    0, 0, NULL, 0, 'budget', 'medium', 'medium', 'medium', 'medium',
                    100, 5, 5, 5, NULL, 't', 't'
                )
                """
            )
            await db.commit()

        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        report = await importer.import_catalog(mode="replace_catalog")
        assert report.ok

        async with aiosqlite.connect(catalog_db) as db:
            cur = await db.execute("SELECT first_name FROM profiles WHERE user_id = 42")
            row = await cur.fetchone()
            assert row[0] == "Test"
            cur = await db.execute("SELECT COUNT(*) FROM recipes WHERE id = 'old'")
            assert (await cur.fetchone())[0] == 0
            cur = await db.execute("SELECT COUNT(*) FROM recipes")
            assert (await cur.fetchone())[0] == 30

    asyncio.run(_run())


def test_invalid_base_servings_rejected():
    bad = {
        "id": "x",
        "slug": "x",
        "name": "x",
        "description": "x",
        "primary_meal_type": "breakfast",
        "meal_types": [{"meal_type": "breakfast", "is_primary": True}],
        "base_servings": 0,
        "yield_weight_g": 100,
        "recommended_portion_min_g": 100,
        "recommended_portion_max_g": 100,
        "scaling_mode": "linear",
        "min_batch_servings": 1,
        "max_batch_servings": 2,
        "prep_time_minutes": 1,
        "cook_time_minutes": 1,
        "active_time_minutes": 1,
        "total_time_minutes": 1,
        "difficulty": "easy",
        "requires_cooking": True,
        "budget_class": "budget",
        "energy_density": "medium",
        "protein_level": "medium",
        "fiber_level": "medium",
        "satiety_level": "medium",
        "calories_per_100g": 1,
        "protein_g_per_100g": 1,
        "fat_g_per_100g": 1,
        "carbs_g_per_100g": 1,
        "ingredients": [
            {
                "ingredient_id": "ing_oats",
                "quantity": 1,
                "unit": "g",
                "quantity_grams": 1,
                "sort_order": 1,
            }
        ],
        "steps": [{"step_number": 1, "instruction": "ok"}],
        "cooking_methods": ["boiling"],
    }
    with pytest.raises(ValidationError):
        RecipeCardSchema.model_validate(bad)


def test_negative_yield_rejected():
    recipes, _, _ = load_catalog_files(CATALOG_ROOT)
    data = recipes[0].model_dump()
    data["yield_weight_g"] = -1
    with pytest.raises(ValidationError):
        RecipeCardSchema.model_validate(data)


def test_score_over_one_rejected():
    with pytest.raises(ValidationError):
        RecipeRelationSchema.model_validate(
            {
                "id": "r",
                "source_recipe_id": "a",
                "target_recipe_id": "b",
                "relation_type": "similar_meal",
                "score": 1.5,
            }
        )


def test_self_relation_rejected():
    with pytest.raises(ValidationError):
        RecipeRelationSchema.model_validate(
            {
                "id": "r",
                "source_recipe_id": "a",
                "target_recipe_id": "a",
                "relation_type": "similar_meal",
                "score": 0.5,
            }
        )


def test_unknown_enum_rejected():
    recipes, _, _ = load_catalog_files(CATALOG_ROOT)
    data = recipes[0].model_dump()
    data["budget_class"] = "luxury"
    with pytest.raises(ValidationError):
        RecipeCardSchema.model_validate(data)


def test_validator_unknown_ingredient_and_missing_image_warning():
    recipes, ingredients_file, _ = load_catalog_files(CATALOG_ROOT)
    data = recipes[0].model_dump()
    data["ingredients"][0]["ingredient_id"] = "ing_does_not_exist"
    data["image_key"] = None
    bad = RecipeCardSchema.model_validate(data)
    report = RecipeCatalogValidator().validate_recipe(
        bad, {i.id for i in ingredients_file.ingredients}
    )
    assert any(e.code == "UNKNOWN_INGREDIENT" for e in report.errors)
    assert any(w.code == "MISSING_IMAGE" for w in report.warnings)


def test_validator_active_without_method():
    recipes, ingredients_file, _ = load_catalog_files(CATALOG_ROOT)
    good = recipes[0]
    report = RecipeCatalogValidator().validate_recipe(
        good.model_copy(update={"cooking_methods": [], "status": RecipeStatus.ACTIVE}),
        {i.id for i in ingredients_file.ingredients},
    )
    assert any(e.code == "ACTIVE_WITHOUT_METHOD" for e in report.errors)


def test_validator_quick_but_slow_warning():
    recipes, ingredients_file, _ = load_catalog_files(CATALOG_ROOT)
    good = recipes[0]
    tags = [RecipeTagSchema.model_validate(t.model_dump()) for t in good.tags]
    tags.append(RecipeTagSchema(tag_type="usage", tag_value="quick"))
    data = good.model_dump()
    data["total_time_minutes"] = 45
    data["prep_time_minutes"] = 10
    data["cook_time_minutes"] = 30
    data["active_time_minutes"] = 20
    data["tags"] = [t.model_dump() for t in tags]
    card = RecipeCardSchema.model_validate(data)
    report = RecipeCatalogValidator().validate_recipe(
        card, {i.id for i in ingredients_file.ingredients}
    )
    assert any(w.code == "QUICK_BUT_SLOW" for w in report.warnings)


def test_validator_leftover_without_storage():
    recipes, ingredients_file, _ = load_catalog_files(CATALOG_ROOT)
    data = recipes[0].model_dump()
    data["leftover_friendly"] = True
    data["storage_days"] = None
    card = RecipeCardSchema.model_validate(data)
    report = RecipeCatalogValidator().validate_recipe(
        card, {i.id for i in ingredients_file.ingredients}
    )
    assert any(w.code == "LEFTOVER_WITHOUT_STORAGE" for w in report.warnings)


def test_validator_missing_meal_type_and_ingredients_and_gap_step():
    recipes, ingredients_file, _ = load_catalog_files(CATALOG_ROOT)
    data = recipes[0].model_dump()
    # gap in steps
    data["steps"] = [
        {"step_number": 1, "instruction": "a", "ingredient_refs": ["1"]},
        {"step_number": 3, "instruction": "b", "ingredient_refs": ["1"]},
    ]
    with pytest.raises(ValidationError):
        RecipeCardSchema.model_validate(data)

    report = RecipeCatalogValidator().validate_recipe(
        recipes[0].model_copy(update={"meal_types": [], "ingredients": []}),
        {i.id for i in ingredients_file.ingredients},
    )
    assert any(e.code == "MISSING_MEAL_TYPE" for e in report.errors)
    assert any(e.code == "MISSING_INGREDIENTS" for e in report.errors)


def test_scaler_linear_discrete_limited_no_mutate(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        repo = RecipeRepository(catalog_db)
        scaler = RecipeScaler()

        oatmeal = await repo.get_recipe_with_dependencies("recipe_oatmeal_banana_001")
        assert oatmeal is not None
        base_qty = oatmeal.ingredients[0].quantity
        scaled = scaler.scale(oatmeal, 4)
        assert scaled.target_servings == Decimal("4")
        assert oatmeal.ingredients[0].quantity == base_qty
        assert scaled.ingredients[0].quantity == base_qty * 2

        omelet = await repo.get_recipe_with_dependencies("recipe_omelet_tomato_cheese_001")
        assert omelet is not None
        assert omelet.scaling_mode == ScalingMode.DISCRETE
        scaled_om = scaler.scale(omelet, 3)
        egg = next(i for i in scaled_om.ingredients if i.ingredient_id == "ing_egg")
        assert egg.quantity >= Decimal("4")

        syrniki = await repo.get_recipe_with_dependencies("recipe_syrniki_001")
        assert syrniki is not None
        assert syrniki.scaling_mode == ScalingMode.LIMITED
        with pytest.raises(RecipeScaleError):
            scaler.scale(syrniki, 20)
        ok = scaler.scale(syrniki, 4)
        assert ok.target_servings == Decimal("4")

        for n in (1, 2, 4, 8):
            s = scaler.scale(oatmeal, n)
            assert s.target_servings == Decimal(str(n))

    asyncio.run(_run())


def test_basket_adapter_aggregates(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        repo = RecipeRepository(catalog_db)
        scaler = RecipeScaler()

        a = await repo.get_recipe_with_dependencies("recipe_oatmeal_banana_001")
        b = await repo.get_recipe_with_dependencies("recipe_yogurt_oats_banana_001")
        assert a and b
        sa = scaler.scale(a, a.base_servings)
        sb = scaler.scale(b, b.base_servings)
        items = recipe_to_normalized_ingredients(a, sa) + recipe_to_normalized_ingredients(
            b, sb
        )
        merged = merge_normalized_for_test(items)
        oat_lines = [
            m
            for m in merged.values()
            if "овсян" in m.display_name.lower() or "овсян" in m.canonical_name
        ]
        assert oat_lines
        assert sum(m.quantity or Decimal("0") for m in oat_lines) >= Decimal("100")

        oat_ing = next(i for i in sa.ingredients if i.ingredient_id == "ing_oats")
        assert oat_ing.quantity_grams == Decimal("80")

    asyncio.run(_run())


def test_repository_filters(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        repo = RecipeRepository(catalog_db)

        breakfasts = await repo.list_by_meal_type(MealType.BREAKFAST)
        assert len(breakfasts) >= 10
        by_goal = await repo.list_by_goal(GoalType.BUDGET, min_score=0.5)
        assert len(by_goal) >= 3
        by_budget = await repo.list_by_budget_class(BudgetClass.VERY_BUDGET)
        assert len(by_budget) >= 3
        quick = await repo.list_by_max_total_time(30)
        assert len(quick) >= 4
        candidates = await repo.find_candidates(
            meal_type=MealType.DINNER,
            max_total_time_minutes=60,
            budget_classes=[BudgetClass.BUDGET, BudgetClass.VERY_BUDGET],
        )
        assert candidates
        full = await repo.get_recipe_with_dependencies(candidates[0].id)
        assert full is not None
        assert full.ingredients
        assert full.steps
        rels = await repo.get_relations(candidates[0].id)
        assert isinstance(rels, list)

    asyncio.run(_run())


def test_invalid_import_does_not_write(tmp_path: Path, catalog_db: Path):
    async def _run() -> None:
        root = tmp_path / "catalog"
        shutil.copytree(CATALOG_ROOT, root)
        bad_file = next((root / "recipes" / "breakfast").glob("*.yaml"))
        data = yaml.safe_load(bad_file.read_text(encoding="utf-8"))
        data["ingredients"][0]["ingredient_id"] = "ing_MISSING_XYZ"
        bad_file.write_text(
            yaml.safe_dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )

        importer = RecipeCatalogImporter(catalog_root=root, db_path=catalog_db)
        report = await importer.import_catalog(mode="upsert")
        assert not report.ok
        assert report.recipes_written == 0

    asyncio.run(_run())
