"""Replacement flow uses deterministic basket rebuild."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from strategy.builder import StrategyBuilder
from strategy.replacement_service import MealReplacementService
from strategy.service import StrategyService
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict
from tests.strategy_fixtures import build_test_profile


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "replace-basket.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
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


def test_replace_flow_rebuilds_basket_without_basket_changes(client, monkeypatch):
    from datetime import date

    plan_start = date.today()
    strategy = StrategyBuilder().build(build_test_profile(days=3))
    menu = annotate_cooking_metadata(build_valid_menu_dict(days=3), strategy)
    strategy_id = asyncio.run(
        StrategyService().save_active_strategy(
            user_id=42,
            strategy=strategy,
            plan_start_date=plan_start,
        )
    )
    menu["strategy_id"] = strategy_id
    menu["plan_start_date"] = plan_start.isoformat()
    _normalize_menu_budget(menu)

    old_basket_names = {
        item["name"]
        for category in menu["basket"]
        for item in category["items"]
    }

    target_id = "day2_dinner"

    async def fake_call(_self, _system, prompt, **_kwargs):
        assert "basket_changes" not in prompt
        return json.dumps(
            {
                "replacement": {
                    "meal": {
                        "type": "dinner",
                        "recipe_name": "Новая запеканка",
                        "meal_id": target_id,
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
            },
            ensure_ascii=False,
        )

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
    updated = response.json()["menu_plan"]
    new_names = {
        item["name"]
        for category in updated["basket"]
        for item in category["items"]
    }
    assert new_names != old_basket_names
    assert updated["total_cost"] == pytest.approx(
        sum(
            item["price"]
            for category in updated["basket"]
            for item in category["items"]
        ),
        rel=0.01,
    )
