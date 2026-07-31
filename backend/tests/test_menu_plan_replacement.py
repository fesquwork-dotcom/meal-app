"""Replacement as an append-only durable revision with optimistic concurrency."""

import asyncio
import json
from datetime import date

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from menu_plan.repository import MenuPlanRepository
from strategy.builder import StrategyBuilder
from strategy.replacement_service import MealReplacementService
from strategy.repository import StrategyRepository
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict
from tests.strategy_fixtures import build_test_profile

TARGET_MEAL_ID = "day2_dinner"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "menu-plan-repl.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _normalize_menu_budget(menu: dict) -> None:
    total = 0.0
    for category in menu.get("basket", []):
        for item in category.get("items", []):
            item["price"] = 50.0
            total += 50.0
    menu["total_cost"] = round(total, 2)


def _setup_durable_plan(menu_plan_id: str = "plan-1"):
    plan_start = date.today()
    strategy = StrategyBuilder().build(build_test_profile(days=3))
    menu = annotate_cooking_metadata(build_valid_menu_dict(days=3), strategy)
    menu["plan_start_date"] = plan_start.isoformat()
    _normalize_menu_budget(menu)
    strategy_id = asyncio.run(
        StrategyRepository().save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=plan_start,
            menu_plan_id=menu_plan_id,
            menu_plan_json=json.dumps(menu, ensure_ascii=False),
        )
    )
    menu["strategy_id"] = strategy_id
    return strategy_id, menu


def _mock_replacement_llm(monkeypatch):
    payload = {
        "replacement": {
            "meal": {
                "type": "dinner",
                "recipe_name": "Новая запеканка",
                "meal_id": TARGET_MEAL_ID,
                "requires_cooking": True,
                "prepared_on_day": 2,
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

    async def fake_call(_self, _system, _prompt, **_kwargs):
        return json.dumps(payload, ensure_ascii=False)

    monkeypatch.setattr(MealReplacementService, "_call_claude", fake_call)


def _replace(client, strategy_id, menu, **extra):
    return client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": TARGET_MEAL_ID,
            **extra,
        },
    )


def test_replacement_appends_durable_revision(client, monkeypatch):
    strategy_id, menu = _setup_durable_plan()
    _mock_replacement_llm(monkeypatch)

    response = _replace(
        client, strategy_id, menu, menu_plan_id="plan-1", expected_revision=1
    )
    assert response.status_code == 200
    body = response.json()
    assert body["menu_plan_id"] == "plan-1"
    assert body["revision"] == 2

    repository = MenuPlanRepository()
    record = asyncio.run(repository.get_by_id("plan-1", 42))
    assert record.current_revision == 2

    revision = asyncio.run(repository.get_revision("plan-1", 2))
    assert revision.change_type == "meal_replacement"
    assert TARGET_MEAL_ID in json.loads(revision.changed_meal_ids_json)
    assert "Новая запеканка" in revision.plan_json

    original = asyncio.run(repository.get_revision("plan-1", 1))
    assert "Новая запеканка" not in original.plan_json
    assert record.original_plan_json == original.plan_json


def test_stale_revision_returns_409(client, monkeypatch):
    strategy_id, menu = _setup_durable_plan()
    _mock_replacement_llm(monkeypatch)

    first = _replace(
        client, strategy_id, menu, menu_plan_id="plan-1", expected_revision=1
    )
    assert first.status_code == 200

    stale = _replace(
        client, strategy_id, menu, menu_plan_id="plan-1", expected_revision=1
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "MENU_PLAN_STALE"

    record = asyncio.run(MenuPlanRepository().get_by_id("plan-1", 42))
    assert record.current_revision == 2


def test_stale_replacement_records_no_memory_event(client, monkeypatch):
    strategy_id, menu = _setup_durable_plan()
    _mock_replacement_llm(monkeypatch)

    _replace(client, strategy_id, menu, menu_plan_id="plan-1", expected_revision=1)
    _replace(
        client,
        strategy_id,
        menu,
        menu_plan_id="plan-1",
        expected_revision=1,
        reason_code="dislike_ingredient",
        target_ingredient="творог",
    )

    async def count_events():
        async with aiosqlite.connect(database.resolve_database_path()) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM memory_events WHERE event_type = 'meal_replaced'"
            )
            return (await cursor.fetchone())[0]

    # Only the first (successful) replacement may have produced an event.
    assert asyncio.run(count_events()) <= 1


def test_legacy_replacement_without_durable_id_still_works(client, monkeypatch):
    strategy_id, menu = _setup_durable_plan()
    _mock_replacement_llm(monkeypatch)

    response = _replace(client, strategy_id, menu)
    assert response.status_code == 200
    body = response.json()
    assert body["menu_plan_id"] is None
    assert body["revision"] is None

    record = asyncio.run(MenuPlanRepository().get_by_id("plan-1", 42))
    assert record.current_revision == 1


def test_menu_plan_id_without_expected_revision_rejected(client, monkeypatch):
    strategy_id, menu = _setup_durable_plan()
    _mock_replacement_llm(monkeypatch)

    response = _replace(client, strategy_id, menu, menu_plan_id="plan-1")
    assert response.status_code == 422


def test_unknown_menu_plan_id_returns_404(client, monkeypatch):
    strategy_id, menu = _setup_durable_plan()
    _mock_replacement_llm(monkeypatch)

    response = _replace(
        client, strategy_id, menu, menu_plan_id="ghost", expected_revision=1
    )
    assert response.status_code == 404
    assert response.json()["code"] == "MENU_PLAN_NOT_FOUND"


def test_menu_plan_bound_to_other_strategy_returns_404(client, monkeypatch):
    strategy_id, menu = _setup_durable_plan("plan-1")
    other_strategy_id, other_menu = _setup_durable_plan("plan-2")
    _mock_replacement_llm(monkeypatch)

    # plan-1 belongs to the first strategy; using it with the second must fail.
    response = _replace(
        client, other_strategy_id, other_menu, menu_plan_id="plan-1", expected_revision=1
    )
    assert response.status_code == 404
    assert response.json()["code"] == "MENU_PLAN_NOT_FOUND"
