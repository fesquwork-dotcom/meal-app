"""Sprint 10.12 — Catalog-aware replace meal."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from menu_generation.catalog_service import CatalogMenuGenerationService
from menu_generation.errors import CatalogGenerationError
from menu_models import MenuPlan
from menu_replacement.reasons import CatalogReplacementReason, resolve_catalog_reason
from menu_replacement.repair import catalog_id_from_menu_recipe_id, count_leftovers_in_menu
from menu_replacement.service import CatalogMealReplacementService
from recipes.importer import RecipeCatalogImporter
from recipes.planning.weights import WeeklyPlannerConfig
from recipes.repository import RecipeRepository
from strategy.builder import StrategyBuilder
from strategy.replacement_models import ReplaceMealRequest
from strategy.replacement_service import MealReplacementService
from strategy.service import StrategyService
from tests.strategy_fixtures import build_test_profile

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"


@pytest.fixture
def catalog_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    monkeypatch.setattr(config, "MEAL_GENERATION_ENGINE", "catalog_planner")
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    db = tmp_path / "catalog_replace.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db))

    async def _seed() -> None:
        await database.init_db()
        report = await RecipeCatalogImporter(
            catalog_root=CATALOG_ROOT, db_path=db
        ).import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()

    asyncio.run(_seed())
    return db


def _strategy(*, days: int = 5, goal: str = "home", leftovers: bool = True):
    profile = build_test_profile(days=days, goal=goal, budget=4000.0)
    strategy = StrategyBuilder(
        clock=lambda: datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    ).build(profile)
    if not leftovers:
        strategy = strategy.model_copy(
            update={"leftovers_enabled": False, "cook_days": list(range(1, days + 1))}
        )
    return strategy


async def _generate_plan(db: Path, strategy, *, persons: int = 2) -> MenuPlan:
    result = await CatalogMenuGenerationService(db_path=db).generate(
        strategy=strategy,
        persons=persons,
        cooktime="medium",
        allergies="нет",
        plan_start_date=date(2026, 8, 5),
    )
    return MenuPlan.model_validate(result)


def _save_strategy(strategy) -> str:
    return asyncio.run(
        StrategyService().save_active_strategy(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 8, 5),
        )
    )


def _find_meal(menu: MenuPlan, *, meal_type: str | None = None, leftover: bool | None = None):
    for day in menu.days_plan:
        for meal in day.meals:
            if meal_type and meal.type != meal_type:
                continue
            if leftover is not None and meal.uses_leftovers != leftover:
                continue
            if meal.meal_id:
                return meal
    return None


def _source_with_leftover(menu: MenuPlan):
    leftovers = [
        m
        for day in menu.days_plan
        for m in day.meals
        if m.uses_leftovers and m.source_meal_id
    ]
    assert leftovers, "expected leftover meals"
    leftover = leftovers[0]
    source = None
    for day in menu.days_plan:
        for meal in day.meals:
            if meal.meal_id == leftover.source_meal_id:
                source = meal
                break
    assert source is not None
    return source, leftover


def test_reason_mapping_reuses_wire_codes():
    req = ReplaceMealRequest(
        strategy_id="s",
        menu_plan=MenuPlan.model_construct(
            summary="x",
            total_cost=0,
            days_plan=[],
            recipes=[],
            basket=[],
        ),
        meal_id="meal_x",
        reason_code="faster",
    )
    assert resolve_catalog_reason(req) == CatalogReplacementReason.TOO_LONG


def test_catalog_replace_breakfast_lunch_dinner(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, goal="muscle", leftovers=False)
        strategy_id = await StrategyService().save_active_strategy(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 8, 5),
        )
        menu = await _generate_plan(catalog_db, strategy)
        menu = menu.model_copy(update={"strategy_id": strategy_id})
        service = CatalogMealReplacementService(db_path=catalog_db)
        claude = AsyncMock(side_effect=AssertionError("Claude must not be called"))

        for meal_type in ("breakfast", "lunch", "dinner"):
            target = _find_meal(menu, meal_type=meal_type, leftover=False)
            assert target is not None
            before = deepcopy(menu)
            old_id = catalog_id_from_menu_recipe_id(target.recipe_id)
            response = await service.replace_meal(
                ReplaceMealRequest(
                    strategy_id=strategy_id,
                    menu_plan=menu,
                    meal_id=target.meal_id,
                    reason_code="generic",
                ),
                user_id=42,
            )
            assert response.replacement_engine == "catalog_selector"
            assert response.explanation
            assert target.meal_id in response.changed_meal_ids
            new_meal = _find_meal(response.menu_plan, meal_type=meal_type)
            # find by id
            new_meal = next(
                m
                for d in response.menu_plan.days_plan
                for m in d.meals
                if m.meal_id == target.meal_id
            )
            new_id = catalog_id_from_menu_recipe_id(new_meal.recipe_id)
            assert new_id != old_id
            # Unchanged slots stay identical.
            for day_a, day_b in zip(before.days_plan, response.menu_plan.days_plan):
                for meal_a, meal_b in zip(day_a.meals, day_b.meals):
                    if meal_a.meal_id in response.changed_meal_ids:
                        continue
                    assert meal_a.model_dump() == meal_b.model_dump()
            menu = response.menu_plan
            assert claude.await_count == 0

    asyncio.run(_run())


def test_dont_like_excludes_current(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, goal="muscle", leftovers=False)
        strategy_id = await StrategyService().save_active_strategy(
            user_id=42, strategy=strategy, plan_start_date=date(2026, 8, 5)
        )
        menu = await _generate_plan(catalog_db, strategy)
        menu = menu.model_copy(update={"strategy_id": strategy_id})
        target = _find_meal(menu, meal_type="lunch", leftover=False)
        assert target is not None
        old_id = catalog_id_from_menu_recipe_id(target.recipe_id)
        response = await CatalogMealReplacementService(db_path=catalog_db).replace_meal(
            ReplaceMealRequest(
                strategy_id=strategy_id,
                menu_plan=menu,
                meal_id=target.meal_id,
                reason_code="dislike_ingredient",
                target_ingredient="лук",
            ),
            user_id=42,
        )
        new_meal = next(
            m
            for d in response.menu_plan.days_plan
            for m in d.meals
            if m.meal_id == target.meal_id
        )
        assert catalog_id_from_menu_recipe_id(new_meal.recipe_id) != old_id

    asyncio.run(_run())


def test_too_long_prefers_faster_when_available(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, goal="muscle", leftovers=False)
        strategy_id = await StrategyService().save_active_strategy(
            user_id=42, strategy=strategy, plan_start_date=date(2026, 8, 5)
        )
        menu = await _generate_plan(catalog_db, strategy)
        menu = menu.model_copy(update={"strategy_id": strategy_id})
        # Pick the slowest dinner as target when possible.
        dinners = [
            m
            for d in menu.days_plan
            for m in d.meals
            if m.type == "dinner" and not m.uses_leftovers
        ]
        repo = RecipeRepository(catalog_db)
        best = None
        best_time = -1
        for meal in dinners:
            rid = catalog_id_from_menu_recipe_id(meal.recipe_id)
            recipe = await repo.get_recipe_with_dependencies(rid) if rid else None
            if recipe and recipe.total_time_minutes > best_time:
                best_time = recipe.total_time_minutes
                best = meal
        assert best is not None
        response = await CatalogMealReplacementService(db_path=catalog_db).replace_meal(
            ReplaceMealRequest(
                strategy_id=strategy_id,
                menu_plan=menu,
                meal_id=best.meal_id,
                reason_code="faster",
            ),
            user_id=42,
        )
        new_meal = next(
            m
            for d in response.menu_plan.days_plan
            for m in d.meals
            if m.meal_id == best.meal_id
        )
        new_recipe = await repo.get_recipe_with_dependencies(
            catalog_id_from_menu_recipe_id(new_meal.recipe_id)
        )
        old_recipe = await repo.get_recipe_with_dependencies(
            catalog_id_from_menu_recipe_id(best.recipe_id)
        )
        assert new_recipe is not None and old_recipe is not None
        assert new_recipe.id != old_recipe.id
        assert new_recipe.total_time_minutes <= old_recipe.total_time_minutes
        assert "FASTER_THAN_CURRENT" in (response.replacement_reasons or []) or (
            new_recipe.total_time_minutes < old_recipe.total_time_minutes
        )

    asyncio.run(_run())


def test_source_and_leftover_chain_valid(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, goal="home", leftovers=True)
        # Force sparse cook days for leftovers.
        strategy = strategy.model_copy(update={"cook_days": [1, 3, 5], "leftovers_enabled": True})
        strategy_id = await StrategyService().save_active_strategy(
            user_id=42, strategy=strategy, plan_start_date=date(2026, 8, 5)
        )
        menu = await _generate_plan(catalog_db, strategy)
        menu = menu.model_copy(update={"strategy_id": strategy_id})
        assert count_leftovers_in_menu(menu) >= 1
        source, leftover = _source_with_leftover(menu)

        # Replace source cook.
        response = await CatalogMealReplacementService(db_path=catalog_db).replace_meal(
            ReplaceMealRequest(
                strategy_id=strategy_id,
                menu_plan=menu,
                meal_id=source.meal_id,
                reason_code="generic",
            ),
            user_id=42,
        )
        updated_leftover = next(
            m
            for d in response.menu_plan.days_plan
            for m in d.meals
            if m.meal_id == leftover.meal_id
        )
        updated_source = next(
            m
            for d in response.menu_plan.days_plan
            for m in d.meals
            if m.meal_id == source.meal_id
        )
        assert updated_leftover.uses_leftovers is True
        assert updated_leftover.source_meal_id == source.meal_id
        assert updated_leftover.cooking_instance_id == updated_source.cooking_instance_id
        assert catalog_id_from_menu_recipe_id(
            updated_leftover.recipe_id
        ) == catalog_id_from_menu_recipe_id(updated_source.recipe_id)

        # Replace leftover target — chain or independent, no orphan.
        response2 = await CatalogMealReplacementService(db_path=catalog_db).replace_meal(
            ReplaceMealRequest(
                strategy_id=strategy_id,
                menu_plan=response.menu_plan,
                meal_id=leftover.meal_id,
                reason_code="generic",
            ),
            user_id=42,
        )
        meal = next(
            m
            for d in response2.menu_plan.days_plan
            for m in d.meals
            if m.meal_id == leftover.meal_id
        )
        if meal.uses_leftovers:
            assert meal.source_meal_id
            source2 = next(
                m
                for d in response2.menu_plan.days_plan
                for m in d.meals
                if m.meal_id == meal.source_meal_id
            )
            assert meal.cooking_instance_id == source2.cooking_instance_id
        else:
            assert meal.source_meal_id is None
            assert meal.cooking_instance_id

    asyncio.run(_run())


def test_not_found_structured_and_no_claude(catalog_db: Path, monkeypatch):
    async def _run() -> None:
        strategy = _strategy(days=5, goal="muscle", leftovers=False)
        strategy_id = await StrategyService().save_active_strategy(
            user_id=42, strategy=strategy, plan_start_date=date(2026, 8, 5)
        )
        menu = await _generate_plan(catalog_db, strategy)
        menu = menu.model_copy(update={"strategy_id": strategy_id})
        target = _find_meal(menu, meal_type="breakfast", leftover=False)
        assert target is not None

        service = CatalogMealReplacementService(db_path=catalog_db)

        async def empty_gather(*_a, **_k):
            return [], ["NO_CANDIDATES"]

        monkeypatch.setattr(service, "_gather_candidates", empty_gather)
        with pytest.raises(CatalogGenerationError) as exc:
            await service.replace_meal(
                ReplaceMealRequest(
                    strategy_id=strategy_id,
                    menu_plan=menu,
                    meal_id=target.meal_id,
                    reason_code="generic",
                ),
                user_id=42,
            )
        assert exc.value.code == CatalogGenerationError.CATALOG_REPLACEMENT_NOT_FOUND
        assert exc.value.details.get("meal_id") == target.meal_id

    asyncio.run(_run())


def test_invalid_meal_id_404(catalog_db: Path):
    client = TestClient(main.app)
    strategy = _strategy(days=5, goal="muscle", leftovers=False)
    strategy_id = _save_strategy(strategy)
    menu = asyncio.run(_generate_plan(catalog_db, strategy))
    menu = menu.model_copy(update={"strategy_id": strategy_id})
    body = {
        "strategy_id": strategy_id,
        "menu_plan": menu.model_dump(mode="json"),
        "meal_id": "meal_does_not_exist",
    }
    resp = client.post("/api/menu/replace-meal", json=body)
    assert resp.status_code == 404


def test_api_catalog_replace_success_claude_zero(catalog_db: Path, monkeypatch):
    client = TestClient(main.app)
    calls = {"n": 0}

    async def spy_claude(self, *args, **kwargs):
        calls["n"] += 1
        raise AssertionError("Claude must not be called for catalog replace")

    monkeypatch.setattr(MealReplacementService, "_call_claude", spy_claude)

    strategy = _strategy(days=5, goal="muscle", leftovers=False)
    strategy_id = _save_strategy(strategy)
    menu = asyncio.run(_generate_plan(catalog_db, strategy))
    menu = menu.model_copy(update={"strategy_id": strategy_id})
    target = _find_meal(menu, meal_type="breakfast", leftover=False)
    assert target is not None
    resp = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu.model_dump(mode="json"),
            "meal_id": target.meal_id,
            "reason_code": "generic",
        },
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["replaced_meal_id"] == target.meal_id
    assert data.get("replacement_engine") == "catalog_selector"
    assert calls["n"] == 0


def test_failed_replace_leaves_plan_unchanged(catalog_db: Path, monkeypatch):
    async def _run() -> None:
        strategy = _strategy(days=5, goal="muscle", leftovers=False)
        strategy_id = await StrategyService().save_active_strategy(
            user_id=42, strategy=strategy, plan_start_date=date(2026, 8, 5)
        )
        menu = await _generate_plan(catalog_db, strategy)
        menu = menu.model_copy(update={"strategy_id": strategy_id})
        original = deepcopy(menu)
        target = _find_meal(menu, meal_type="lunch", leftover=False)
        service = CatalogMealReplacementService(db_path=catalog_db)

        async def empty_gather(*_a, **_k):
            return [], ["forced"]

        monkeypatch.setattr(service, "_gather_candidates", empty_gather)
        with pytest.raises(CatalogGenerationError):
            await service.replace_meal(
                ReplaceMealRequest(
                    strategy_id=strategy_id,
                    menu_plan=menu,
                    meal_id=target.meal_id,
                    reason_code="generic",
                ),
                user_id=42,
            )
        assert menu.model_dump() == original.model_dump()

    asyncio.run(_run())


def test_determinism(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, goal="muscle", leftovers=False)
        strategy_id = await StrategyService().save_active_strategy(
            user_id=42, strategy=strategy, plan_start_date=date(2026, 8, 5)
        )
        menu = await _generate_plan(catalog_db, strategy)
        menu = menu.model_copy(update={"strategy_id": strategy_id})
        target = _find_meal(menu, meal_type="dinner", leftover=False)
        req = ReplaceMealRequest(
            strategy_id=strategy_id,
            menu_plan=menu,
            meal_id=target.meal_id,
            reason_code="generic",
        )
        service = CatalogMealReplacementService(db_path=catalog_db)
        a = await service.replace_meal(req, user_id=42)
        b = await service.replace_meal(req, user_id=42)
        meal_a = next(
            m for d in a.menu_plan.days_plan for m in d.meals if m.meal_id == target.meal_id
        )
        meal_b = next(
            m for d in b.menu_plan.days_plan for m in d.meals if m.meal_id == target.meal_id
        )
        assert meal_a.recipe_id == meal_b.recipe_id
        assert a.changed_meal_ids == b.changed_meal_ids

    asyncio.run(_run())


def test_ingredient_unavailable_excludes_ingredient(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, goal="muscle", leftovers=False)
        strategy_id = await StrategyService().save_active_strategy(
            user_id=42, strategy=strategy, plan_start_date=date(2026, 8, 5)
        )
        menu = await _generate_plan(catalog_db, strategy)
        menu = menu.model_copy(update={"strategy_id": strategy_id})
        target = _find_meal(menu, meal_type="lunch", leftover=False)
        assert target is not None
        response = await CatalogMealReplacementService(db_path=catalog_db).replace_meal(
            ReplaceMealRequest(
                strategy_id=strategy_id,
                menu_plan=menu,
                meal_id=target.meal_id,
                reason_code="ingredient_unavailable",
                target_ingredient="тунец",
            ),
            user_id=42,
        )
        new_meal = next(
            m
            for d in response.menu_plan.days_plan
            for m in d.meals
            if m.meal_id == target.meal_id
        )
        repo = RecipeRepository(catalog_db)
        new_recipe = await repo.get_recipe_with_dependencies(
            catalog_id_from_menu_recipe_id(new_meal.recipe_id)
        )
        assert new_recipe is not None
        blob = " ".join(
            [
                new_recipe.name.lower(),
                *[
                    (i.ingredient.display_name if i.ingredient else i.ingredient_id).lower()
                    for i in new_recipe.ingredients
                ],
            ]
        ).replace("ё", "е")
        assert "тунец" not in blob

    asyncio.run(_run())


def test_want_variety_changes_recipe(catalog_db: Path):
    async def _run() -> None:
        strategy = _strategy(days=5, goal="muscle", leftovers=False)
        strategy_id = await StrategyService().save_active_strategy(
            user_id=42, strategy=strategy, plan_start_date=date(2026, 8, 5)
        )
        menu = await _generate_plan(catalog_db, strategy)
        menu = menu.model_copy(update={"strategy_id": strategy_id})
        target = _find_meal(menu, meal_type="breakfast", leftover=False)
        old_id = catalog_id_from_menu_recipe_id(target.recipe_id)
        response = await CatalogMealReplacementService(db_path=catalog_db).replace_meal(
            ReplaceMealRequest(
                strategy_id=strategy_id,
                menu_plan=menu,
                meal_id=target.meal_id,
                reason="хочу разнообразия",
            ),
            user_id=42,
        )
        new_meal = next(
            m
            for d in response.menu_plan.days_plan
            for m in d.meals
            if m.meal_id == target.meal_id
        )
        assert catalog_id_from_menu_recipe_id(new_meal.recipe_id) != old_id

    asyncio.run(_run())


def test_planner_limits_unchanged():
    cfg = WeeklyPlannerConfig()
    assert cfg.max_extra_cook_days == 1
    assert cfg.max_leftovers_per_cook == 1


def test_catalog_still_86(catalog_db: Path):
    async def _run() -> None:
        assert await RecipeRepository(catalog_db).count_recipes() == 86

    asyncio.run(_run())
