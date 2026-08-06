"""Sprint 10.8 — Source workflow, comparison, drafts, catalog expansion."""

from __future__ import annotations

import asyncio
from pathlib import Path

import aiosqlite
import pytest
from pydantic import ValidationError

from recipes.enums import MealType
from recipes.importer import RecipeCatalogImporter
from recipes.quality.duplicate_check import RecipeDuplicateChecker
from recipes.quality.enums import CreationMethod, QualityStatus, SourceType
from recipes.quality.gate import RecipeQualityGate
from recipes.quality.source_comparison import (
    RecipeSourceComparison,
    is_forbidden_source_reference,
    validate_observation,
)
from recipes.quality.source_draft import SourceBackedDraftBuilder
from recipes.quality.source_models import (
    IngredientObservation,
    RecipeConcept,
    RecipeSourceObservation,
)
from recipes.quality.source_review import RecipeSourceReviewer
from recipes.repository import RecipeRepository
from recipes.schemas import RecipeSourceFileSchema
from recipes.selection.context import CandidateSelectionContext
from recipes.selection.selector import RecipeCandidateSelector
from recipes.selection.weights import DEFAULT_SCORING_WEIGHTS

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"

NEW_RECIPE_IDS = {
    "recipe_turkey_veg_lunch_skillet_001",
    "recipe_chicken_veg_lunch_skillet_001",
    "recipe_chickpea_tomato_skillet_001",
    "recipe_egg_spinach_scramble_lunch_001",
    "recipe_tuna_bean_salad_lunch_001",
    "recipe_beef_cabbage_skillet_lunch_001",
    "recipe_beans_tomato_egg_lunch_001",
    "recipe_chicken_zucchini_dinner_skillet_001",
    "recipe_chickpea_spinach_dinner_001",
    "recipe_egg_veg_wrap_flex_001",
}


@pytest.fixture
def catalog_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENVIRONMENT", "test")
    import config

    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    return tmp_path / "sources.db"


def _obs(
    source_id: str,
    reference: str,
    *,
    title: str = "Source",
    ingredients: list[tuple[str, float | None]] | None = None,
    method: str = "frying",
    total: int = 25,
    cook: int = 15,
    servings: float = 2,
) -> RecipeSourceObservation:
    ings = [
        IngredientObservation(name=n, quantity_grams=g)
        for n, g in (ingredients or [("turkey", 400.0), ("onion", 100.0)])
    ]
    return RecipeSourceObservation(
        source_id=source_id,
        source_type=SourceType.CULINARY_WEBSITE,
        source_title=title,
        source_reference=reference,
        publisher_or_author="Test Publisher",
        accessed_at="2026-08-04",
        ingredients=ings,
        cooking_method=method,
        prep_time_minutes=10,
        cook_time_minutes=cook,
        total_time_minutes=total,
        yield_servings=servings,
        supports_ingredients=True,
        supports_proportions=True,
        supports_method=True,
        supports_time=True,
        supports_yield=True,
    )


def test_fake_empty_reference_rejected():
    assert "empty_or_placeholder_reference" in is_forbidden_source_reference("n/a")
    assert "empty_or_placeholder_reference" in is_forbidden_source_reference("")
    with pytest.raises(ValidationError):
        RecipeSourceFileSchema(
            source_type=SourceType.CULINARY_WEBSITE,
            source_title="x",
            source_reference="https://example.com",
        )


def test_llm_cannot_be_source():
    errs = is_forbidden_source_reference(
        "chatgpt://session/1", title="LLM generated recipe"
    )
    assert "llm_cannot_be_source" in errs


def test_observation_parsing_and_min_two_sources():
    concept = RecipeConcept(
        concept_id="c1",
        title="Turkey skillet",
        target_meal_types=["lunch"],
        primary_protein="turkey",
    )
    one = [_obs("s1", "https://www.bbc.co.uk/food/recipes/mincedturkeystirfrie_90232")]
    cmp = RecipeSourceComparison()
    result = cmp.compare(concept, one)
    assert any(q.startswith("need_at_least_2") for q in result.unresolved_questions)

    two = one + [
        _obs(
            "s2",
            "https://www.bbcgoodfood.com/recipes/turkey-chilli",
            title="Turkey chilli",
        )
    ]
    result2 = cmp.compare(concept, two)
    assert not any(q.startswith("need_at_least_2") for q in result2.unresolved_questions)
    assert "turkey" in result2.ingredient_consensus


def test_duplicate_source_detection():
    concept = RecipeConcept(
        concept_id="c1", title="X", target_meal_types=["lunch"], primary_protein="turkey"
    )
    ref = "https://www.bbc.co.uk/food/recipes/mincedturkeystirfrie_90232"
    result = RecipeSourceComparison().compare(
        concept, [_obs("s1", ref), _obs("s2", ref, title="Dup")]
    )
    assert "duplicate_source_reference" in result.unresolved_questions


def test_comparison_disagreement_and_draft_blocking():
    concept = RecipeConcept(
        concept_id="c1",
        title="Conflict",
        target_meal_types=["lunch"],
        primary_protein="turkey",
    )
    obs = [
        _obs(
            "s1",
            "https://www.example-publisher.org/a",
            method="baking",
            total=90,
            cook=80,
            ingredients=[("turkey", 400)],
        ),
        _obs(
            "s2",
            "https://www.other-publisher.org/b",
            method="no_cook salad",
            total=10,
            cook=0,
            ingredients=[("turkey", 100)],
        ),
    ]
    # example-publisher is fine; not example.com exact placeholder
    draft = SourceBackedDraftBuilder().build(concept, obs)
    assert draft.comparison is not None
    assert draft.comparison.critical_contradiction or draft.blocking_reasons
    assert draft.ready_for_catalog_import is False


def test_normalized_draft_ready_when_sources_agree():
    concept = RecipeConcept(
        concept_id="c1",
        title="Turkey skillet",
        target_meal_types=["lunch"],
        primary_protein="turkey",
        max_total_time_minutes=30,
    )
    obs = [
        _obs(
            "s1",
            "https://www.bbc.co.uk/food/recipes/mincedturkeystirfrie_90232",
            ingredients=[("turkey", 400), ("onion", 100), ("oil", 15)],
            total=25,
        ),
        _obs(
            "s2",
            "https://www.bbcgoodfood.com/recipes/turkey-chilli",
            ingredients=[("turkey", 450), ("onion", 120), ("oil", 20)],
            total=30,
        ),
    ]
    draft = SourceBackedDraftBuilder().build(concept, obs)
    assert draft.ready_for_catalog_import is True
    assert draft.normalized_method
    assert draft.normalized_total_time_minutes is not None
    assert len(draft.normalized_ingredients) >= 2


def test_unresolved_blocking_question_on_missing_protein():
    concept = RecipeConcept(
        concept_id="c1",
        title="Missing protein",
        target_meal_types=["lunch"],
        primary_protein="fish",
    )
    obs = [
        _obs(
            "s1",
            "https://www.bbc.co.uk/food/recipes/mincedturkeystirfrie_90232",
            ingredients=[("turkey", 400)],
        ),
        _obs(
            "s2",
            "https://www.bbcgoodfood.com/recipes/turkey-chilli",
            ingredients=[("turkey", 400)],
        ),
    ]
    draft = SourceBackedDraftBuilder().build(concept, obs)
    assert draft.ready_for_catalog_import is False
    assert any("primary_protein" in r for r in draft.blocking_reasons)


def test_source_verified_transition_and_no_source_cannot(catalog_db: Path):
    async def _inner() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        report = await importer.import_catalog(mode="replace_catalog")
        assert report.ok
        repo = RecipeRepository(catalog_db)
        recipes = await repo.list_active()
        by_id = {r.id: r for r in recipes}

        # New source-backed recipe should import as source_verified with >=2 sources
        new = by_id["recipe_turkey_veg_lunch_skillet_001"]
        async with aiosqlite.connect(catalog_db) as db:
            db.row_factory = aiosqlite.Row
            cur = await db.execute(
                "SELECT quality_status, creation_method, source_count FROM recipe_provenance WHERE recipe_id=?",
                (new.id,),
            )
            row = dict(await cur.fetchone())
            assert row["creation_method"] == CreationMethod.SOURCE_ADAPTED.value
            assert row["source_count"] >= 2
            assert row["quality_status"] == QualityStatus.SOURCE_VERIFIED.value

            cur = await db.execute(
                "SELECT COUNT(*) FROM recipe_sources WHERE recipe_id=?", (new.id,)
            )
            assert (await cur.fetchone())[0] >= 2

            gate = RecipeQualityGate()
            applied = await gate.evaluate(new, db, mode="apply")
            assert applied.current_quality_status != QualityStatus.APPROVED
            assert applied.approval_eligible is False
            assert not applied.blocking_errors

            reviewed_existing = {
                "recipe_oatmeal_banana_001",
                "recipe_omelet_tomato_cheese_001",
                "recipe_buckwheat_chicken_veg_001",
                "recipe_lentil_soup_001",
                "recipe_baked_chicken_veg_001",
            }
            plain = next(
                r
                for r in recipes
                if r.id not in NEW_RECIPE_IDS and r.id not in reviewed_existing
            )
            cur = await db.execute(
                "SELECT source_count FROM recipe_provenance WHERE recipe_id=?",
                (plain.id,),
            )
            sc = (await cur.fetchone())[0]
            assert sc == 0
            result = await gate.evaluate(plain, db, mode="apply")
            assert result.current_quality_status != QualityStatus.SOURCE_VERIFIED
            assert result.source_summary["source_verified"] is False

    asyncio.run(_inner())


def test_catalog_80_and_sprint108_new_recipes_provenance(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        repo = RecipeRepository(catalog_db)
        assert await repo.count_recipes() == 86
        recipes = await repo.list_active()
        ids = {r.id for r in recipes}
        assert NEW_RECIPE_IDS.issubset(ids)
        assert len(NEW_RECIPE_IDS) == 10

        lunch_new = [
            r
            for r in recipes
            if r.id in NEW_RECIPE_IDS and r.primary_meal_type == MealType.LUNCH
        ]
        assert len(lunch_new) >= 7

        async with aiosqlite.connect(catalog_db) as db:
            for rid in NEW_RECIPE_IDS:
                cur = await db.execute(
                    """
                    SELECT creation_method, quality_status, source_count
                    FROM recipe_provenance WHERE recipe_id=?
                    """,
                    (rid,),
                )
                row = await cur.fetchone()
                assert row is not None
                assert row[0] == CreationMethod.SOURCE_ADAPTED.value
                assert row[2] >= 2
                cur = await db.execute(
                    "SELECT COUNT(*) FROM recipe_sources WHERE recipe_id=?", (rid,)
                )
                assert (await cur.fetchone())[0] >= 2

            gate = RecipeQualityGate()
            for rid in NEW_RECIPE_IDS:
                recipe = next(r for r in recipes if r.id == rid)
                result = await gate.evaluate(recipe, db, mode="read_only")
                assert not result.blocking_errors

    asyncio.run(_run())


def test_idempotent_import(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        r1 = await importer.import_catalog(mode="replace_catalog")
        r2 = await importer.import_catalog(mode="upsert")
        assert r1.ok and r2.ok
        repo = RecipeRepository(catalog_db)
        assert await repo.count_recipes() == 86

    asyncio.run(_run())


def test_duplicate_recipe_protection(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        repo = RecipeRepository(catalog_db)
        oatmeal = await repo.get_recipe_with_dependencies("recipe_oatmeal_banana_001")
        assert oatmeal is not None
        existing = [oatmeal]
        concept = RecipeConcept(
            concept_id="dup_oatmeal",
            title="Овсяная каша с бананом",
            target_meal_types=["breakfast"],
            primary_protein="dairy",
        )
        draft = SourceBackedDraftBuilder().build(
            concept,
            [
                _obs(
                    "s1",
                    "https://www.bbcgoodfood.com/recipes/perfect-porridge",
                    ingredients=[("oats", 80), ("milk", 300), ("banana", 120)],
                    method="boiling",
                    total=15,
                ),
                _obs(
                    "s2",
                    "https://www.bbcgoodfood.com/recipes/budget-porridge",
                    ingredients=[("oats", 85), ("milk", 250), ("banana", 100)],
                    method="boiling",
                    total=17,
                ),
            ],
            ingredient_id_map={
                "oats": "ing_oats",
                "milk": "ing_milk",
                "banana": "ing_banana",
            },
        )
        check = RecipeDuplicateChecker().check(
            concept=concept,
            existing=existing,
            draft=draft,
            proposed_meal_types={"breakfast"},
        )
        assert check.is_duplicate
        assert check.matched_recipe_id == "recipe_oatmeal_banana_001"

    asyncio.run(_run())


def test_source_review_existing_seed(catalog_db: Path):
    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        repo = RecipeRepository(catalog_db)
        recipe = await repo.get_recipe_with_dependencies("recipe_oatmeal_banana_001")
        assert recipe is not None
        observations = [
            _obs(
                "s1",
                "https://www.bbcgoodfood.com/recipes/perfect-porridge",
                ingredients=[("oats", 50), ("milk", 350)],
                method="boiling",
                total=10,
                cook=5,
                servings=1,
            ),
            _obs(
                "s2",
                "https://www.bbcgoodfood.com/recipes/budget-porridge",
                ingredients=[("oats", 85), ("milk", 250)],
                method="boiling",
                total=15,
                cook=5,
                servings=2,
            ),
        ]
        result = RecipeSourceReviewer().review(recipe, observations)
        assert result.passed
        assert result.source_count == 2

    asyncio.run(_run())


def test_selector_weights_unchanged(catalog_db: Path):
    assert DEFAULT_SCORING_WEIGHTS.goal == 0.25

    async def _run() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=catalog_db)
        await importer.import_catalog(mode="replace_catalog")
        selector = RecipeCandidateSelector(db_path=catalog_db)
        result = await selector.select(
            CandidateSelectionContext(meal_type=MealType.LUNCH, limit=5, max_total_time_minutes=30)
        )
        assert result.returned_count >= 1

    asyncio.run(_run())


def test_validate_observation_rejects_empty():
    bad = RecipeSourceObservation(
        source_id="",
        source_type=SourceType.CULINARY_WEBSITE,
        source_title="",
        source_reference="none",
    )
    errs = validate_observation(bad)
    assert errs
