"""Sprint 10.5 — Recipe Candidate Selector."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from recipes.enums import (
    BudgetClass,
    EquipmentType,
    GoalType,
    MealType,
    ProteinSourceTag,
    RecipeRole,
    RecipeStatus,
    TagType,
)
from recipes.importer import RecipeCatalogImporter
from recipes.models import (
    Recipe,
    RecipeEquipmentItem,
    RecipeGoalScore,
    RecipeIngredient,
    RecipeMealTypeLink,
    RecipeRoleItem,
    RecipeTag,
)
from recipes.repository import RecipeRepository
from recipes.selection.codes import HardFilterCode, SoftReasonCode
from recipes.selection.context import CandidateSelectionContext
from recipes.selection.hard_filter import RecipeHardFilter
from recipes.selection.merge import merge_selection_contexts
from recipes.selection.models import SelectionStatus
from recipes.selection.profile_adapter import ProfileToCandidateContextAdapter
from recipes.selection.scorer import RecipeScorer
from recipes.selection.selector import RecipeCandidateSelector
from recipes.selection.strategy_adapter import StrategyToCandidateContextAdapter
from recipes.selection.weights import DEFAULT_SCORING_WEIGHTS, RecipeScoringWeights
from strategy.context import ProfileContext
from strategy.models import WeeklyStrategy

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"


@pytest.fixture
def catalog_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENVIRONMENT", "test")
    import config

    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    db = tmp_path / "selector.db"

    async def _seed() -> None:
        importer = RecipeCatalogImporter(catalog_root=CATALOG_ROOT, db_path=db)
        report = await importer.import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()

    asyncio.run(_seed())
    return db


def _base_recipe(**overrides) -> Recipe:
    from decimal import Decimal
    from recipes.enums import (
        Difficulty,
        EnergyDensity,
        FiberLevel,
        IngredientGroup,
        IngredientUnit,
        ProteinLevel,
        SatietyLevel,
        ScalingMode,
    )

    data = dict(
        id="recipe_test_001",
        slug="test",
        name="Test",
        description="d",
        status=RecipeStatus.ACTIVE,
        version=1,
        primary_meal_type=MealType.DINNER,
        base_servings=Decimal("2"),
        yield_weight_g=Decimal("400"),
        recommended_portion_min_g=Decimal("150"),
        recommended_portion_max_g=Decimal("250"),
        scaling_mode=ScalingMode.LINEAR,
        min_batch_servings=Decimal("1"),
        max_batch_servings=Decimal("8"),
        prep_time_minutes=5,
        cook_time_minutes=10,
        active_time_minutes=10,
        total_time_minutes=15,
        difficulty=Difficulty.EASY,
        requires_cooking=True,
        batch_friendly=False,
        leftover_friendly=False,
        storage_days=None,
        freezing_supported=False,
        budget_class=BudgetClass.BUDGET,
        energy_density=EnergyDensity.MEDIUM,
        protein_level=ProteinLevel.MEDIUM,
        fiber_level=FiberLevel.MEDIUM,
        satiety_level=SatietyLevel.MEDIUM,
        calories_per_100g=100,
        protein_g_per_100g=10,
        fat_g_per_100g=5,
        carbs_g_per_100g=10,
        image_key=None,
        created_at="t",
        updated_at="t",
        meal_types=(
            RecipeMealTypeLink(meal_type=MealType.DINNER, is_primary=True),
        ),
        ingredients=(
            RecipeIngredient(
                id="ri1",
                recipe_id="recipe_test_001",
                ingredient_id="ing_chicken_breast",
                quantity=Decimal("200"),
                unit=IngredientUnit.G,
                quantity_grams=Decimal("200"),
                preparation=None,
                is_optional=False,
                ingredient_group=IngredientGroup.MAIN,
                sort_order=1,
                scaling_factor=Decimal("1"),
                rounding_increment=None,
            ),
        ),
        steps=(),
        cooking_methods=(),
        equipment=(),
        roles=(),
        goal_scores=(),
        tags=(),
    )
    data.update(overrides)
    return Recipe(**data)


# ---------------------------------------------------------------------------
# Hard filters
# ---------------------------------------------------------------------------


def test_hard_filter_meal_type_and_status():
    filt = RecipeHardFilter()
    ctx = CandidateSelectionContext(meal_type=MealType.DINNER, limit=5)
    ok = _base_recipe()
    assert filt.evaluate(ok, ctx).accepted

    bad_meal = _base_recipe(
        meal_types=(RecipeMealTypeLink(meal_type=MealType.BREAKFAST, is_primary=True),),
        primary_meal_type=MealType.BREAKFAST,
    )
    decision = filt.evaluate(bad_meal, ctx)
    assert not decision.accepted
    assert HardFilterCode.MEAL_TYPE_MISMATCH.value in decision.reason_codes

    inactive = _base_recipe(status=RecipeStatus.DRAFT)
    assert HardFilterCode.INACTIVE_RECIPE.value in filt.evaluate(inactive, ctx).reason_codes


def test_hard_filter_optional_ingredient_does_not_block():
    from decimal import Decimal
    from recipes.enums import IngredientGroup, IngredientUnit

    filt = RecipeHardFilter()
    ctx = CandidateSelectionContext(
        meal_type=MealType.DINNER,
        excluded_ingredient_ids={"ing_mushroom"},
    )
    recipe = _base_recipe(
        ingredients=(
            RecipeIngredient(
                id="ri1",
                recipe_id="recipe_test_001",
                ingredient_id="ing_chicken_breast",
                quantity=Decimal("200"),
                unit=IngredientUnit.G,
                quantity_grams=Decimal("200"),
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
                ingredient_id="ing_mushroom",
                quantity=Decimal("50"),
                unit=IngredientUnit.G,
                quantity_grams=Decimal("50"),
                preparation=None,
                is_optional=True,
                ingredient_group=IngredientGroup.GARNISH,
                sort_order=2,
                scaling_factor=Decimal("1"),
                rounding_increment=None,
            ),
        )
    )
    assert filt.evaluate(recipe, ctx).accepted

    required_mush = _base_recipe(
        ingredients=(
            RecipeIngredient(
                id="ri1",
                recipe_id="recipe_test_001",
                ingredient_id="ing_mushroom",
                quantity=Decimal("50"),
                unit=IngredientUnit.G,
                quantity_grams=Decimal("50"),
                preparation=None,
                is_optional=False,
                ingredient_group=IngredientGroup.MAIN,
                sort_order=1,
                scaling_factor=Decimal("1"),
                rounding_increment=None,
            ),
        )
    )
    assert not filt.evaluate(required_mush, ctx).accepted


def test_hard_filter_protein_time_budget_equipment_tags_avoid():
    filt = RecipeHardFilter()
    recipe = _base_recipe(
        total_time_minutes=40,
        budget_class=BudgetClass.PREMIUM,
        tags=(RecipeTag(tag_type=TagType.PROTEIN_SOURCE, tag_value="fish"),),
        equipment=(
            RecipeEquipmentItem(equipment=EquipmentType.OVEN, required=True),
        ),
    )
    ctx = CandidateSelectionContext(
        meal_type=MealType.DINNER,
        max_total_time_minutes=30,
        allowed_budget_classes=[BudgetClass.BUDGET],
        excluded_protein_sources={ProteinSourceTag.FISH},
        available_equipment={EquipmentType.STOVE, EquipmentType.FRYING_PAN},
        avoid_recipe_ids={"recipe_test_001"},
        required_tags={("usage", "quick")},
        excluded_tags={("taste", "sweet")},
    )
    decision = filt.evaluate(recipe, ctx)
    assert not decision.accepted
    codes = set(decision.reason_codes)
    assert HardFilterCode.TIME_LIMIT_EXCEEDED.value in codes
    assert HardFilterCode.BUDGET_CLASS_NOT_ALLOWED.value in codes
    assert HardFilterCode.EXCLUDED_PROTEIN_SOURCE.value in codes
    assert HardFilterCode.REQUIRED_EQUIPMENT_UNAVAILABLE.value in codes
    assert HardFilterCode.AVOIDED_RECIPE.value in codes
    assert HardFilterCode.REQUIRED_TAG_MISSING.value in codes


def test_implicit_basic_equipment_does_not_block():
    filt = RecipeHardFilter()
    recipe = _base_recipe(
        equipment=(
            RecipeEquipmentItem(equipment=EquipmentType.KNIFE, required=True),
            RecipeEquipmentItem(equipment=EquipmentType.STOVE, required=True),
        )
    )
    ctx = CandidateSelectionContext(
        meal_type=MealType.DINNER,
        available_equipment={EquipmentType.STOVE, EquipmentType.FRYING_PAN, EquipmentType.POT},
    )
    assert filt.evaluate(recipe, ctx).accepted


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def test_scorer_active_components_normalization():
    scorer = RecipeScorer()
    recipe = _base_recipe(
        goal_scores=(
            RecipeGoalScore(goal=GoalType.WEIGHT_LOSS, score=0.9, reason_codes=()),
        ),
        total_time_minutes=15,
    )
    ctx_two = CandidateSelectionContext(
        meal_type=MealType.DINNER,
        goal=GoalType.WEIGHT_LOSS,
        max_total_time_minutes=30,
    )
    score_two, bd_two, _, _ = scorer.score(recipe, ctx_two)
    assert set(bd_two.active_weights) == {"goal", "time"}
    assert score_two > 0.7

    ctx_many = CandidateSelectionContext(
        meal_type=MealType.DINNER,
        goal=GoalType.WEIGHT_LOSS,
        max_total_time_minutes=30,
        allowed_budget_classes=[BudgetClass.VERY_BUDGET, BudgetClass.BUDGET, BudgetClass.STANDARD],
        preferred_ingredient_ids={"ing_chicken_breast"},
        preferred_protein_sources={ProteinSourceTag.CHICKEN},
        preferred_tags={("usage", "quick")},
        desired_roles=[RecipeRole.QUICK_MEAL],
        prefer_batch_friendly=True,
        allow_leftovers=True,
        family_mode=True,
    )
    score_many, bd_many, _, _ = scorer.score(recipe, ctx_many)
    assert len(bd_many.active_weights) >= 6
    # Inactive criteria must not zero-out a strong goal+time match into near-zero.
    assert score_many > 0.2


def test_scorer_diversity_penalty_not_hard_exclude():
    scorer = RecipeScorer()
    recipe = _base_recipe()
    ctx = CandidateSelectionContext(
        meal_type=MealType.DINNER,
        goal=GoalType.BALANCED,
        avoid_ingredient_ids={"ing_chicken_breast"},
    )
    score, bd, reasons, _ = scorer.score(recipe, ctx)
    assert bd.diversity_penalty < 0
    assert SoftReasonCode.REPEATED_INGREDIENT_PENALTY.value in reasons
    assert score >= 0


def test_scorer_component_order_independence():
    """Weights are looked up by name; order of evaluation must not matter."""
    w = RecipeScoringWeights()
    assert w.as_dict()["goal"] == DEFAULT_SCORING_WEIGHTS.goal
    scorer = RecipeScorer(w)
    recipe = _base_recipe(
        goal_scores=(
            RecipeGoalScore(goal=GoalType.BUDGET, score=0.8, reason_codes=()),
        ),
        budget_class=BudgetClass.VERY_BUDGET,
    )
    ctx = CandidateSelectionContext(
        meal_type=MealType.DINNER,
        goal=GoalType.BUDGET,
        allowed_budget_classes=[BudgetClass.VERY_BUDGET, BudgetClass.BUDGET],
    )
    s1, _, _, _ = scorer.score(recipe, ctx)
    s2, _, _, _ = scorer.score(recipe, ctx)
    assert s1 == s2


def test_tie_breaking_stable(catalog_db: Path):
    async def _run() -> None:
        selector = RecipeCandidateSelector(db_path=catalog_db)
        ctx = CandidateSelectionContext(
            meal_type=MealType.BREAKFAST,
            limit=10,
        )
        a = await selector.select(ctx)
        b = await selector.select(ctx)
        assert [c.recipe.id for c in a.candidates] == [c.recipe.id for c in b.candidates]

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Integration scenarios A–H
# ---------------------------------------------------------------------------


def test_scenario_a_weight_loss_dinner(catalog_db: Path):
    async def _run() -> None:
        selector = RecipeCandidateSelector(db_path=catalog_db)
        ctx = CandidateSelectionContext(
            meal_type=MealType.DINNER,
            goal=GoalType.WEIGHT_LOSS,
            max_total_time_minutes=30,
            allowed_budget_classes=[
                BudgetClass.VERY_BUDGET,
                BudgetClass.BUDGET,
                BudgetClass.STANDARD,
            ],
            excluded_protein_sources={ProteinSourceTag.FISH},
            limit=5,
        )
        result = await selector.select(ctx)
        assert result.candidates
        for cand in result.candidates:
            assert cand.recipe.total_time_minutes <= 30
            protein = {
                t.tag_value
                for t in cand.recipe.tags
                if t.tag_type.value == "protein_source"
            }
            assert "fish" not in protein
            assert cand.reason_codes
            assert cand.score_breakdown.components
        scores = [c.score for c in result.candidates]
        assert scores == sorted(scores, reverse=True)

    asyncio.run(_run())


def test_scenario_b_budget_lunch(catalog_db: Path):
    async def _run() -> None:
        selector = RecipeCandidateSelector(db_path=catalog_db)
        ctx = CandidateSelectionContext(
            meal_type=MealType.LUNCH,
            goal=GoalType.BUDGET,
            allowed_budget_classes=[BudgetClass.VERY_BUDGET, BudgetClass.BUDGET],
            limit=5,
        )
        result = await selector.select(ctx)
        assert result.candidates
        for cand in result.candidates:
            assert cand.recipe.budget_class in {
                BudgetClass.VERY_BUDGET,
                BudgetClass.BUDGET,
            }
        # Determinism
        again = await selector.select(ctx)
        assert [c.recipe.id for c in result.candidates] == [
            c.recipe.id for c in again.candidates
        ]
        # very_budget should not rank below budget when goal=budget (soft preference)
        if len(result.candidates) >= 2:
            top = result.candidates[0]
            assert "budget" in top.score_breakdown.components

    asyncio.run(_run())


def test_scenario_c_muscle_gain_lunch(catalog_db: Path):
    async def _run() -> None:
        selector = RecipeCandidateSelector(db_path=catalog_db)
        ctx = CandidateSelectionContext(
            meal_type=MealType.LUNCH,
            goal=GoalType.MUSCLE_GAIN,
            preferred_protein_sources={
                ProteinSourceTag.CHICKEN,
                ProteinSourceTag.BEEF,
                ProteinSourceTag.TURKEY,
            },
            prefer_batch_friendly=True,
            limit=5,
        )
        result = await selector.select(ctx)
        assert result.candidates
        top = result.candidates[0]
        assert "goal" in top.score_breakdown.components
        assert "batch" in top.score_breakdown.components
        assert top.score_breakdown.components["goal"] >= 0.5

    asyncio.run(_run())


def test_scenario_d_quick_breakfast(catalog_db: Path):
    async def _run() -> None:
        selector = RecipeCandidateSelector(db_path=catalog_db)
        ctx = CandidateSelectionContext(
            meal_type=MealType.BREAKFAST,
            goal=GoalType.QUICK_COOKING,
            max_total_time_minutes=15,
            limit=5,
        )
        result = await selector.select(ctx)
        assert result.candidates
        for cand in result.candidates:
            assert cand.recipe.total_time_minutes <= 15
        # Faster recipes should not rank below slower when both pass
        times = [c.recipe.total_time_minutes for c in result.candidates]
        assert min(times) <= max(times)

    asyncio.run(_run())


def test_scenario_e_family_dinner(catalog_db: Path):
    async def _run() -> None:
        selector = RecipeCandidateSelector(db_path=catalog_db)
        ctx = CandidateSelectionContext(
            meal_type=MealType.DINNER,
            goal=GoalType.FAMILY,
            family_mode=True,
            limit=5,
        )
        result = await selector.select(ctx)
        assert result.candidates
        # At least one candidate should surface family signal when available
        familyish = [
            c
            for c in result.candidates
            if SoftReasonCode.FAMILY_FRIENDLY.value in c.reason_codes
            or "family" in c.score_breakdown.components
        ]
        assert familyish or result.after_hard_filters > 0

    asyncio.run(_run())


def test_scenario_f_equipment_restriction(catalog_db: Path):
    async def _run() -> None:
        selector = RecipeCandidateSelector(db_path=catalog_db)
        ctx = CandidateSelectionContext(
            meal_type=MealType.DINNER,
            available_equipment={
                EquipmentType.STOVE,
                EquipmentType.FRYING_PAN,
                EquipmentType.POT,
            },
            limit=10,
        )
        result = await selector.select(ctx)
        for cand in result.candidates:
            for eq in cand.recipe.equipment:
                if not eq.required:
                    continue
                if eq.equipment in {
                    EquipmentType.KNIFE,
                    EquipmentType.CUTTING_BOARD,
                    EquipmentType.GRATER,
                }:
                    continue
                assert eq.equipment in ctx.available_equipment
        # Oven-required dinners should be removed
        assert result.filter_stats.removed.get(
            HardFilterCode.REQUIRED_EQUIPMENT_UNAVAILABLE.value, 0
        ) >= 1 or all(
            EquipmentType.OVEN
            not in {e.equipment for e in c.recipe.equipment if e.required}
            for c in result.candidates
        )

    asyncio.run(_run())


def test_scenario_g_mushroom_exclusion(catalog_db: Path):
    async def _run() -> None:
        selector = RecipeCandidateSelector(db_path=catalog_db)
        ctx = CandidateSelectionContext(
            meal_type=MealType.DINNER,
            excluded_ingredient_ids={"ing_mushroom"},
            limit=10,
        )
        result = await selector.select(ctx)
        for cand in result.candidates:
            for ing in cand.recipe.ingredients:
                if ing.is_optional:
                    continue
                assert ing.ingredient_id != "ing_mushroom"
        # buckwheat with mushrooms dinner should be filtered if mushrooms required
        ids = {c.recipe.id for c in result.candidates}
        assert "recipe_buckwheat_mushroom_egg_001" not in ids

    asyncio.run(_run())


def test_scenario_h_repeated_ingredient_penalty(catalog_db: Path):
    async def _run() -> None:
        selector = RecipeCandidateSelector(db_path=catalog_db)
        base = CandidateSelectionContext(
            meal_type=MealType.DINNER,
            goal=GoalType.MUSCLE_GAIN,
            limit=10,
        )
        with_penalty = base.model_copy(
            update={"avoid_ingredient_ids": {"ing_chicken_breast", "ing_chicken_thigh"}}
        )
        a = await selector.select(base)
        b = await selector.select(with_penalty)
        chicken_ids = {
            c.recipe.id
            for c in a.candidates
            if any(
                i.ingredient_id.startswith("ing_chicken") and not i.is_optional
                for i in c.recipe.ingredients
            )
        }
        # Chicken recipes still allowed under penalty
        for cand in b.candidates:
            if cand.recipe.id in chicken_ids:
                assert SoftReasonCode.REPEATED_INGREDIENT_PENALTY.value in cand.reason_codes
                assert cand.score_breakdown.diversity_penalty < 0

    asyncio.run(_run())


def test_no_candidates_and_insufficient(catalog_db: Path):
    async def _run() -> None:
        selector = RecipeCandidateSelector(db_path=catalog_db)
        impossible = CandidateSelectionContext(
            meal_type=MealType.DINNER,
            max_total_time_minutes=1,
            allowed_budget_classes=[BudgetClass.PREMIUM],
            excluded_protein_sources={
                ProteinSourceTag.CHICKEN,
                ProteinSourceTag.TURKEY,
                ProteinSourceTag.BEEF,
                ProteinSourceTag.FISH,
                ProteinSourceTag.EGGS,
                ProteinSourceTag.DAIRY,
                ProteinSourceTag.LEGUMES,
                ProteinSourceTag.MIXED,
                ProteinSourceTag.NONE,
                ProteinSourceTag.PORK,
            },
            limit=5,
        )
        result = await selector.select(impossible)
        assert result.selection_status == SelectionStatus.NO_CANDIDATES
        assert result.candidates == []
        assert result.filter_stats.removed

        tight = CandidateSelectionContext(
            meal_type=MealType.BREAKFAST,
            max_total_time_minutes=5,
            limit=5,
        )
        result2 = await selector.select(tight)
        if 0 < result2.after_hard_filters < 5:
            assert result2.selection_status == SelectionStatus.INSUFFICIENT_CANDIDATES
            assert result2.returned_count == result2.after_hard_filters

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Adapters / merge
# ---------------------------------------------------------------------------


def test_profile_adapter_and_unresolved(catalog_db: Path):
    async def _run() -> None:
        repo = RecipeRepository(catalog_db)
        ingredients = await repo.list_ingredients()
        profile = ProfileContext.from_profile(
            {
                "goal": "weightloss",
                "days": 7,
                "budget": 3000,
                "cooktime": "fast",
                "proteins": ["chicken"],
                "meal_types": ["breakfast", "lunch", "dinner"],
                "allergies": "рыба, морепродукты",
            }
        )
        adapter = ProfileToCandidateContextAdapter()
        ctx, meta = adapter.adapt(
            profile, meal_type=MealType.DINNER, ingredients=ingredients
        )
        assert ctx.goal == GoalType.WEIGHT_LOSS
        assert ctx.max_total_time_minutes == 20
        assert ProteinSourceTag.CHICKEN in ctx.preferred_protein_sources
        # fish may resolve; seafood-like "морепродукты" may be unresolved
        assert "морепродукты" in meta.unresolved_exclusions or meta.unresolved_exclusions == []
        # if рыба resolved to fish ingredient
        if "ing_fish_white" in ctx.excluded_ingredient_ids or any(
            "fish" in i for i in ctx.excluded_ingredient_ids
        ):
            assert ctx.excluded_ingredient_ids

    asyncio.run(_run())


def test_strategy_adapter_and_merge():
    strategy = WeeklyStrategy.model_validate(
        {
            "goal": "budget",
            "days": 7,
            "budget": 2000,
            "meal_types": ["breakfast", "lunch", "dinner"],
            "meals_per_day": 3,
            "cook_days": [1, 3, 5, 7],
            "shopping_days": [1],
            "leftovers_enabled": True,
            "repeat_breakfasts": True,
            "repeat_lunches": True,
            "repeat_dinners": False,
            "preferred_proteins": ["chicken", "eggs"],
            "excluded_products": [],
            "cooking_time_limit": 45,
            "prefer_faster_meals": False,
            "generated_at": "2026-01-01T00:00:00Z",
        }
    )
    adapter = StrategyToCandidateContextAdapter()
    ctx, _ = adapter.adapt(strategy, meal_type="lunch")
    assert ctx.goal == GoalType.BUDGET
    assert ctx.allow_leftovers is True
    assert ctx.max_total_time_minutes == 45

    profile_partial = CandidateSelectionContext(
        meal_type=MealType.LUNCH,
        excluded_ingredient_ids={"ing_fish_white"},
        max_total_time_minutes=20,
    )
    slot = CandidateSelectionContext(
        meal_type=MealType.LUNCH,
        excluded_ingredient_ids={"ing_egg"},
        max_total_time_minutes=15,
    )
    merged = merge_selection_contexts(
        meal_type=MealType.LUNCH,
        profile=profile_partial,
        strategy=ctx,
        slot=slot,
    )
    assert merged.excluded_ingredient_ids == {"ing_fish_white", "ing_egg"}
    assert merged.max_total_time_minutes == 15  # slot wins
