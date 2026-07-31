"""API and pipeline tests for POST /api/menu/replace-meal."""

import asyncio
from copy import deepcopy

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from menu_models import MenuPlan
from strategy.builder import StrategyBuilder
from strategy.replacement_service import MealReplacementService
from strategy.service import StrategyService
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict
from tests.strategy_fixtures import build_test_profile


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "replace-meal.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _build_strategy_menu(strategy_id: str):
    from datetime import date

    strategy = StrategyBuilder().build(build_test_profile(days=3))
    menu = annotate_cooking_metadata(build_valid_menu_dict(days=3), strategy)
    menu["strategy_id"] = strategy_id
    menu["plan_start_date"] = date.today().isoformat()
    return strategy, menu


def _save_strategy(strategy, strategy_id: str | None = None):
    from datetime import date

    service = StrategyService()
    return asyncio.run(
        service.save_active_strategy(
            user_id=42,
            strategy=strategy,
            plan_start_date=date.today(),
        )
    )


def _replacement_llm_payload(target_meal_id: str, target_type: str, day_num: int):
    return {
        "replacement": {
            "meal": {
                "type": target_type,
                "recipe_name": "Новая запеканка",
                "meal_id": target_meal_id,
                "requires_cooking": True,
                "prepared_on_day": day_num,
                "uses_leftovers": False,
                "source_meal_id": None,
            },
            "recipe": {
                "name": "Новая запеканка",
                "emoji": "🥘",
                "cook_time": "30 мин",
                "kbju": "Б:20г Ж:10г У:30г",
                "ingredients": [
                    {"name": "творог", "amount": "300 г"},
                    {"name": "яйца", "amount": "2 шт"},
                ],
                "steps": ["Смешать", "Запечь"],
            },
        },
        "affected_meals": [],
    }


def _normalize_menu_budget(menu: dict) -> None:
    total = 0.0
    for category in menu.get("basket", []):
        for item in category.get("items", []):
            item["price"] = 50.0
            total += 50.0
    menu["total_cost"] = round(total, 2)


def test_replace_meal_success(client, monkeypatch):
    strategy, menu = _build_strategy_menu("pending")
    strategy_id = _save_strategy(strategy)
    menu["strategy_id"] = strategy_id
    _normalize_menu_budget(menu)
    target_id = "day2_dinner"

    async def fake_call(_self, _system, _prompt, **_kwargs):
        import json

        return json.dumps(_replacement_llm_payload(target_id, "dinner", 2), ensure_ascii=False)

    monkeypatch.setattr(MealReplacementService, "_call_claude", fake_call)

    async def _count_strategies():
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM weekly_strategies")
            return (await cursor.fetchone())[0]

    before_count = asyncio.run(_count_strategies())

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": target_id,
            "reason": "Хочу проще",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["replaced_meal_id"] == target_id
    assert target_id in body["changed_meal_ids"]
    assert body["menu_plan"]["strategy_id"] == strategy_id

    updated = body["menu_plan"]
    dinner = next(
        meal
        for day in updated["days_plan"]
        for meal in day["meals"]
        if meal.get("meal_id") == target_id
    )
    assert dinner["recipe_name"] == "Новая запеканка"
    assert asyncio.run(_count_strategies()) == before_count


def test_replace_meal_foreign_strategy_returns_404(client, monkeypatch):
    strategy, menu = _build_strategy_menu("pending")
    strategy_id = _save_strategy(strategy)
    menu["strategy_id"] = strategy_id

    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day1_breakfast",
        },
    )
    assert response.status_code == 404


def test_replace_meal_not_found_returns_404(client, monkeypatch):
    strategy, menu = _build_strategy_menu("pending")
    strategy_id = _save_strategy(strategy)
    menu["strategy_id"] = strategy_id

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "missing_meal",
        },
    )
    assert response.status_code == 404


def test_replace_meal_completed_strategy_returns_409(client, monkeypatch):
    from datetime import date, timedelta

    strategy, menu = _build_strategy_menu("pending")
    past = date.today() - timedelta(days=10)
    strategy_id = asyncio.run(
        StrategyService().save_active_strategy(
            user_id=42,
            strategy=strategy,
            plan_start_date=past,
        )
    )
    menu["strategy_id"] = strategy_id
    menu["plan_start_date"] = past.isoformat()

    llm_called = False

    async def fake_call(_self, _system, _prompt, **_kwargs):
        nonlocal llm_called
        llm_called = True
        return "{}"

    monkeypatch.setattr(MealReplacementService, "_call_claude", fake_call)

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day1_breakfast",
        },
    )
    assert response.status_code == 409
    assert llm_called is False


def test_replace_meal_strategy_id_mismatch_returns_422(client):
    strategy, menu = _build_strategy_menu("pending")
    strategy_id = _save_strategy(strategy)

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": {**menu, "strategy_id": "wrong"},
            "meal_id": "day1_breakfast",
        },
    )
    assert response.status_code == 422


def test_replace_meal_reason_too_long_returns_422(client):
    strategy, menu = _build_strategy_menu("pending")
    strategy_id = _save_strategy(strategy)
    menu["strategy_id"] = strategy_id

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day1_breakfast",
            "reason": "x" * 500,
        },
    )
    assert response.status_code == 422


def test_original_menu_not_mutated(client, monkeypatch):
    strategy, menu = _build_strategy_menu("pending")
    strategy_id = _save_strategy(strategy)
    menu["strategy_id"] = strategy_id
    _normalize_menu_budget(menu)
    original = deepcopy(menu)
    target_id = "day1_lunch"

    async def fake_call(_self, _system, _prompt, **_kwargs):
        import json

        return json.dumps(_replacement_llm_payload(target_id, "lunch", 1), ensure_ascii=False)

    monkeypatch.setattr(MealReplacementService, "_call_claude", fake_call)

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": target_id,
        },
    )
    assert response.status_code == 200

    original_plan = MenuPlan.model_validate(original)
    current_lunch = original_plan.days_plan[0].meals[1]
    assert current_lunch.recipe_name == original["days_plan"][0]["meals"][1]["recipe_name"]
