"""Sprint 10.7 — Recipe Quality, Provenance & Pattern Evidence."""

from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path

import aiosqlite
import pytest
from pydantic import ValidationError

from recipes.db import ensure_recipe_catalog_tables
from recipes.enums import (
    BudgetClass,
    CookingMethod,
    Difficulty,
    EnergyDensity,
    FiberLevel,
    GoalType,
    IngredientGroup,
    IngredientUnit,
    MealType,
    ProteinLevel,
    RecipeStatus,
    SatietyLevel,
    ScalingMode,
    TagType,
)
from recipes.importer import RecipeCatalogImporter
from recipes.models import Recipe, RecipeIngredient, RecipeMealTypeLink, RecipeStep, RecipeTag
from recipes.quality.audit import RecipeQualityAuditor
from recipes.quality.confidence import RecipeQualityConfidenceCalculator
from recipes.quality.enums import (
    CreationMethod,
    EvidenceType,
    PatternType,
    QualityStatus,
    ReviewOutcome,
    SourceType,
)
from recipes.quality.filters import meets_minimum_quality
from recipes.quality.gate import RecipeQualityGate
from recipes.quality.nutrition import RecipeNutritionCalculator
from recipes.quality.pattern_deriver import RecipePatternDeriver
from recipes.quality.proportion_checker import RecipeProportionChecker
from recipes.quality.provenance import ProvenanceStore
from recipes.quality.time_checker import RecipeTimeChecker
from recipes.quality.yield_checker import RecipeYieldChecker
from recipes.repository import RecipeRepository
from recipes.schemas import RecipeCardSchema, RecipeProvenanceFileSchema, RecipeSourceFileSchema
from recipes.selection.context import CandidateSelectionContext
from recipes.selection.selector import RecipeCandidateSelector
from recipes.selection.weights import DEFAULT_SCORING_WEIGHTS

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"


@pytest.fixture
def catalog_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENVIRONMENT", "test")
    import config

    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    return tmp_path / "quality.db"


def _minimal_recipe(**overrides) -> Recipe:
    data = dict(
        id="recipe_test_001",
        slug="test-recipe",
        name="Test",
        description="Test recipe",
        status=RecipeStatus.ACTIVE,
        version=1,
        primary_meal_type=MealType.BREAKFAST,
        base_servings=Decimal("2"),
        yield_weight_g=Decimal("500"),
        recommended_portion_min_g=Decimal("200"),
        recommended_portion_max_g=Decimal("300"),
        scaling_mode=ScalingMode.LINEAR,
        min_batch_servings=Decimal("1"),
        max_batch_servings=Decimal("8"),
        prep_time_minutes=5,
        cook_time_minutes=10,
        active_time_minutes=8,
        total_time_minutes=15,
        difficulty=Difficulty.EASY,
        requires_cooking=True,
        batch_friendly=True,
        leftover_friendly=True,
        storage_days=3,
        freezing_supported=False,
        budget_class=BudgetClass.BUDGET,
        energy_density=EnergyDensity.MEDIUM,
        protein_level=ProteinLevel.MEDIUM,
        fiber_level=FiberLevel.MEDIUM,
        satiety_level=SatietyLevel.MEDIUM,
        calories_per_100g=120.0,
        protein_g_per_100g=8.0,
        fat_g_per_100g=4.0,
        carbs_g_per_100g=14.0,
        image_key=None,
        created_at="2026-01-01T00:00:00+00:00",
        updated_at="2026-01-01T00:00:00+00:00",
        meal_types=(
            RecipeMealTypeLink(meal_type=MealType.BREAKFAST, is_primary=True),
        ),
        ingredients=(
            RecipeIngredient(
                id="ri1",
                recipe_id="recipe_test_001",
                ingredient_id="ing_oats",
                quantity=Decimal("80"),
                unit=IngredientUnit.G,
                quantity_grams=Decimal("80"),
                preparation=None,
                is_optional=False,
                ingredient_group=IngredientGroup.MAIN,
                sort_order=1,
                scaling_factor=Decimal("1"),
                rounding_increment=None,
            ),
            RecipeIngredient(
                id="ri2",
                recipe_id="recipe_test_001",
                ingredient_id="ing_milk",
                quantity=Decimal("300"),
                unit=IngredientUnit.ML,
                quantity_grams=Decimal("300"),
                preparation=None,
                is_optional=False,
                ingredient_group=IngredientGroup.MAIN,
                sort_order=2,
                scaling_factor=Decimal("1"),
                rounding_increment=None,
            ),
            RecipeIngredient(
                id="ri3",
                recipe_id="recipe_test_001",
                ingredient_id="ing_salt",
                quantity=Decimal("1"),
                unit=IngredientUnit.G,
                quantity_grams=Decimal("1"),
                preparation=None,
                is_optional=True,
                ingredient_group=IngredientGroup.SEASONING,
                sort_order=3,
                scaling_factor=Decimal("1"),
                rounding_increment=None,
            ),
        ),
        steps=(
            RecipeStep(
                id="s1",
                recipe_id="recipe_test_001",
                step_number=1,
                instruction="Cook",
                duration_minutes=10,
                active_minutes=5,
                temperature_c=None,
            ),
        ),
        cooking_methods=(CookingMethod.BOILING,),
        tags=(),
        roles=(),
        goal_scores=(),
        equipment=(),
    )
    data.update(overrides)
    return Recipe(**data)


def test_provenance_agent_generated_without_sources(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        report = await importer.import_catalog(mode="replace_catalog")
        assert report.ok
        async with aiosqlite.connect(catalog_db) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute("SELECT COUNT(*) AS c FROM recipe_provenance")
            assert (await cur.fetchone())["c"] == 30
            cur = await db.execute(
                """
                SELECT creation_method, quality_status, source_count
                FROM recipe_provenance LIMIT 1
                """
            )
            row = await cur.fetchone()
            assert row["creation_method"] == CreationMethod.AGENT_GENERATED.value
            assert row["quality_status"] == QualityStatus.SCHEMA_VALIDATED.value
            assert row["source_count"] == 0
            cur = await db.execute("SELECT COUNT(*) AS c FROM recipe_sources")
            assert (await cur.fetchone())["c"] == 0

    asyncio.run(_run())


def test_source_verified_without_sources_rejected():
    with pytest.raises(ValidationError):
        RecipeProvenanceFileSchema(
            creation_method=CreationMethod.SOURCE_ADAPTED,
            quality_status=QualityStatus.SOURCE_VERIFIED,
            sources=[],
        )


def test_empty_source_reference_rejected():
    with pytest.raises(ValidationError):
        RecipeSourceFileSchema(
            source_type=SourceType.CULINARY_WEBSITE,
            source_title="Example",
            source_reference="https://example.com",
        )


def test_source_count_matches_records(catalog_db: Path):
    async def _run() -> None:
        store = ProvenanceStore()
        async with aiosqlite.connect(catalog_db) as db:
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
                    'r1','r1','n','d','active',1,'breakfast',
                    1,100,80,120,'linear',1,4,1,1,1,2,'easy',1,
                    0,0,NULL,0,'budget','medium','medium','medium','medium',
                    100,5,3,10,NULL,'t','t'
                )
                """
            )
            await store.ensure_default_provenance(db, "r1")
            await db.execute(
                """
                INSERT INTO recipe_sources (
                    recipe_id, source_type, source_title, source_reference,
                    supports_ingredients, supports_proportions, supports_method,
                    supports_time, supports_yield, supports_storage, created_at
                ) VALUES ('r1','cookbook','Book','ISBN 978-0-00-000000-0',1,1,1,0,0,0,'t')
                """
            )
            await store.ensure_default_provenance(db, "r1")
            prov = await store.get_provenance(db, "r1")
            assert prov["source_count"] == 1
            await db.commit()

    asyncio.run(_run())


def test_approved_and_kitchen_transition_rules():
    store = ProvenanceStore()
    assert store.validate_quality_transition(
        quality_status=QualityStatus.APPROVED,
        source_count=1,
        has_human_or_expert_review=False,
        has_kitchen_test_passed=False,
        notes="x",
        approved_by="human",
        approved_at="t",
    )
    assert store.validate_quality_transition(
        quality_status=QualityStatus.KITCHEN_TESTED,
        source_count=0,
        has_human_or_expert_review=False,
        has_kitchen_test_passed=False,
        notes=None,
        approved_by=None,
        approved_at=None,
    )


def test_pattern_quick_and_mismatch():
    deriver = RecipePatternDeriver()
    quick = _minimal_recipe(total_time_minutes=25)
    result = deriver.derive(quick)
    ev = next(e for e in result.evidence if e.pattern_type == PatternType.QUICK_MEAL)
    assert ev.value_bool is True
    assert any(w.code == "DERIVED_QUICK_TAG_MISSING" for w in result.warnings)

    slow = _minimal_recipe(
        total_time_minutes=45,
        tags=(RecipeTag(tag_type=TagType.USAGE, tag_value="quick"),),
    )
    result2 = deriver.derive(slow)
    assert any(w.code == "TAG_QUICK_NOT_SUPPORTED" for w in result2.warnings)


def test_pattern_batch_leftover_budget_fiber_family_freezer():
    deriver = RecipePatternDeriver()
    recipe = _minimal_recipe()
    result = deriver.derive(recipe)
    by_type = {e.pattern_type: e for e in result.evidence}

    assert by_type[PatternType.BATCH_FRIENDLY].value_bool is True
    assert by_type[PatternType.BATCH_FRIENDLY].evidence_json["check_kind"] == (
        "structural_not_culinary_safety"
    )

    leftover_bad = _minimal_recipe(leftover_friendly=True, storage_days=None)
    r2 = deriver.derive(leftover_bad)
    assert any(i.code == "LEFTOVER_WITHOUT_STORAGE" for i in r2.inconsistencies)

    assert by_type[PatternType.HIGH_FIBER].evidence_type == EvidenceType.INSUFFICIENT_DATA
    assert any(w.code == "FIBER_DATA_UNAVAILABLE" for w in result.warnings)

    assert by_type[PatternType.BUDGET_FRIENDLY].evidence_type == EvidenceType.DECLARED
    assert any(w.code == "BUDGET_NOT_PRICE_VERIFIED" for w in result.warnings)

    fam = by_type[PatternType.FAMILY_FRIENDLY]
    assert (fam.score or 0) <= 0.7

    freezer = by_type[PatternType.FREEZER_FRIENDLY]
    assert freezer.evidence_type == EvidenceType.DECLARED
    assert freezer.rule_code == "FREEZER_DECLARED_ONLY"


def test_high_protein_and_energy_density():
    deriver = RecipePatternDeriver()
    high = _minimal_recipe(
        protein_g_per_100g=15.0,
        calories_per_100g=140.0,
        carbs_g_per_100g=5.0,
        fat_g_per_100g=5.0,
        energy_density=EnergyDensity.HIGH,
    )
    result = deriver.derive(high)
    by_type = {e.pattern_type: e for e in result.evidence}
    assert by_type[PatternType.HIGH_PROTEIN].value_bool is True
    assert by_type[PatternType.LOW_ENERGY_DENSITY].value_bool is True
    assert any(w.code == "ENERGY_DENSITY_MISMATCH" for w in result.warnings)


def test_nutrition_snapshot_and_no_invention(catalog_db: Path):
    calc = RecipeNutritionCalculator()
    ok = _minimal_recipe(
        calories_per_100g=120.0,
        protein_g_per_100g=8.0,
        fat_g_per_100g=4.0,
        carbs_g_per_100g=14.0,
    )
    snap = calc.check_snapshot(ok)
    assert snap.status in {"passed", "warning"}

    bad = _minimal_recipe(
        calories_per_100g=500.0,
        protein_g_per_100g=8.0,
        fat_g_per_100g=4.0,
        carbs_g_per_100g=14.0,
    )
    snap2 = calc.check_snapshot(bad)
    assert any(i.code == "NUTRITION_MACRO_KCAL_MISMATCH" for i in snap2.issues)

    neg = _minimal_recipe(protein_g_per_100g=-1.0)
    snap3 = calc.check_snapshot(neg)
    assert any(i.code == "NUTRITION_NEGATIVE_VALUE" for i in snap3.issues)

    async def _ing() -> None:
        async with aiosqlite.connect(catalog_db) as db:
            await ensure_recipe_catalog_tables(db)
            result = await calc.calculate_from_ingredients(ok, db)
            assert result.status == "insufficient_data"
            assert any(
                i.code == "NUTRITION_INGREDIENT_DATA_INCOMPLETE" for i in result.issues
            )

    asyncio.run(_ing())


def test_yield_time_proportion_checks():
    y = RecipeYieldChecker().check(_minimal_recipe())
    assert y.metrics.get("plausibility") in {"plausible", "suspicious", "insufficient_data"}

    outside = RecipeYieldChecker().check(
        _minimal_recipe(
            yield_weight_g=Decimal("1000"),
            recommended_portion_min_g=Decimal("100"),
            recommended_portion_max_g=Decimal("150"),
        )
    )
    assert any(
        i.code == "BASE_PORTION_OUTSIDE_RECOMMENDED_RANGE" for i in outside.issues
    )

    t = RecipeTimeChecker().check(
        _minimal_recipe(active_time_minutes=40, total_time_minutes=20)
    )
    assert any(i.code == "ACTIVE_TIME_INCONSISTENT" for i in t.issues)

    baking = RecipeTimeChecker().check(
        _minimal_recipe(
            cooking_methods=(CookingMethod.BAKING,),
            cook_time_minutes=5,
            total_time_minutes=20,
        )
    )
    assert any(i.code == "COOKING_METHOD_TIME_SUSPICIOUS" for i in baking.issues)
    assert any(i.code == "TEMPERATURE_MISSING_FOR_BAKING" for i in baking.issues)

    oily = _minimal_recipe(
        ingredients=(
            RecipeIngredient(
                id="ri1",
                recipe_id="recipe_test_001",
                ingredient_id="ing_chicken",
                quantity=Decimal("100"),
                unit=IngredientUnit.G,
                quantity_grams=Decimal("100"),
                preparation=None,
                is_optional=False,
                ingredient_group=IngredientGroup.MAIN,
                sort_order=1,
                scaling_factor=Decimal("1"),
                rounding_increment=None,
            ),
            RecipeIngredient(
                id="ri2",
                recipe_id="recipe_test_001",
                ingredient_id="ing_oil",
                quantity=Decimal("40"),
                unit=IngredientUnit.G,
                quantity_grams=Decimal("40"),
                preparation=None,
                is_optional=False,
                ingredient_group=IngredientGroup.SAUCE,
                sort_order=2,
                scaling_factor=Decimal("1"),
                rounding_increment=None,
            ),
        )
    )
    prop = RecipeProportionChecker().check(oily)
    assert any(i.code == "OIL_RATIO_SUSPICIOUS" for i in prop.issues)

    dry = _minimal_recipe(
        cooking_methods=(CookingMethod.BOILING,),
        ingredients=(
            RecipeIngredient(
                id="ri1",
                recipe_id="recipe_test_001",
                ingredient_id="ing_rice",
                quantity=Decimal("100"),
                unit=IngredientUnit.G,
                quantity_grams=Decimal("100"),
                preparation=None,
                is_optional=False,
                ingredient_group=IngredientGroup.MAIN,
                sort_order=1,
                scaling_factor=Decimal("1"),
                rounding_increment=None,
            ),
        ),
    )
    prop2 = RecipeProportionChecker().check(dry)
    assert any(i.code == "DRY_GRAIN_LIQUID_NOT_FOUND" for i in prop2.issues)


def test_quality_gate_cannot_approve(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        repo = RecipeRepository(catalog_db)
        recipe = await repo.get_recipe_with_dependencies("recipe_oatmeal_banana_001")
        assert recipe is not None
        gate = RecipeQualityGate()
        async with aiosqlite.connect(catalog_db) as db:
            db.row_factory = aiosqlite.Row
            await ensure_recipe_catalog_tables(db)
            read = await gate.evaluate(recipe, db, mode="read_only")
            assert read.suggested_quality_status in {
                QualityStatus.SCHEMA_VALIDATED,
                QualityStatus.COMPUTATIONALLY_CHECKED,
            }
            assert read.suggested_quality_status != QualityStatus.APPROVED
            assert read.approval_eligible is False

            applied = await gate.evaluate(recipe, db, mode="apply")
            assert applied.current_quality_status in {
                QualityStatus.SCHEMA_VALIDATED,
                QualityStatus.COMPUTATIONALLY_CHECKED,
            }
            assert applied.current_quality_status != QualityStatus.SOURCE_VERIFIED
            await db.commit()

            store = ProvenanceStore()
            prov = await store.get_provenance(db, recipe.id)
            assert prov["quality_status"] != QualityStatus.APPROVED.value
            assert prov["quality_status"] != QualityStatus.SOURCE_VERIFIED.value

    asyncio.run(_run())


def test_audit_all_30_no_approved_read_only(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")

        async with aiosqlite.connect(catalog_db) as db:
            cur = await db.execute(
                "SELECT quality_status FROM recipe_provenance LIMIT 1"
            )
            before = (await cur.fetchone())[0]

        auditor = RecipeQualityAuditor(db_path=catalog_db)
        report = await auditor.run(mode="read_only")
        assert report.recipe_count == 30
        assert report.approved_count == 0
        assert report.source_verified_count == 0
        assert report.human_reviewed_count == 0
        assert report.kitchen_tested_count == 0
        assert all(
            r.suggested_quality_status != QualityStatus.APPROVED for r in report.results
        )
        assert all(
            int(r.source_summary.get("source_count") or 0) == 0 for r in report.results
        )

        async with aiosqlite.connect(catalog_db) as db:
            cur = await db.execute(
                "SELECT DISTINCT quality_status FROM recipe_provenance"
            )
            statuses = {row[0] for row in await cur.fetchall()}
            # read_only may create provenance but must not raise to approved
            assert "approved" not in statuses
            # recipe content unchanged — provenance may still be schema_validated
            assert before == QualityStatus.SCHEMA_VALIDATED.value

        out = catalog_db.parent / "QUALITY_REPORT.md"
        auditor.write_markdown(report, out)
        text = out.read_text(encoding="utf-8")
        assert "agent_generated" in text
        assert "Approved" in text or "approved" in text

        payload = report.to_dict()
        assert "results" in payload
        json.dumps(payload)  # stable serializable

    asyncio.run(_run())


def test_audit_apply_idempotent(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        auditor = RecipeQualityAuditor(db_path=catalog_db)
        r1 = await auditor.run(mode="apply")
        r2 = await auditor.run(mode="apply")
        assert r1.recipe_count == r2.recipe_count == 30
        assert r1.approved_count == r2.approved_count == 0
        async with aiosqlite.connect(catalog_db) as db:
            cur = await db.execute(
                """
                SELECT quality_status, COUNT(*) AS c
                FROM recipe_provenance GROUP BY quality_status
                """
            )
            dist = {row[0]: row[1] for row in await cur.fetchall()}
            assert "approved" not in dist
            assert "source_verified" not in dist
            total = sum(dist.values())
            assert total == 30

    asyncio.run(_run())


def test_confidence_caps():
    calc = RecipeQualityConfidenceCalculator()
    score = calc.calculate(
        quality_status=QualityStatus.SCHEMA_VALIDATED,
        source_count=0,
        blocking_errors=[],
        warnings=[],
    )
    assert score <= 0.30
    score2 = calc.calculate(
        quality_status=QualityStatus.COMPUTATIONALLY_CHECKED,
        source_count=0,
        blocking_errors=[],
        warnings=[],
    )
    assert score2 <= 0.50


def test_selector_weights_unchanged_and_context_optional(catalog_db: Path):
    assert DEFAULT_SCORING_WEIGHTS.goal == 0.25
    ctx = CandidateSelectionContext(meal_type=MealType.BREAKFAST)
    assert ctx.minimum_quality_status is None
    assert meets_minimum_quality(None, None) is True

    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        selector = RecipeCandidateSelector(db_path=catalog_db)
        result = await selector.select(
            CandidateSelectionContext(meal_type=MealType.BREAKFAST, limit=5)
        )
        assert result.returned_count >= 1

    asyncio.run(_run())


def test_import_still_idempotent_with_provenance(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        await importer.import_catalog(mode="upsert")
        repo = RecipeRepository(catalog_db)
        assert await repo.count_recipes() == 30
        async with aiosqlite.connect(catalog_db) as db:
            cur = await db.execute("SELECT COUNT(*) FROM recipe_provenance")
            assert (await cur.fetchone())[0] == 30

    asyncio.run(_run())
