"""Integration tests: replacement flow feeding the Memory Engine (non-critical)."""

from __future__ import annotations

import asyncio
import json

import aiosqlite
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
    db_path = tmp_path / "replace-memory.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _prepare(strategy_id: str = "pending"):
    from datetime import date

    plan_start = date.today()
    strategy = StrategyBuilder().build(build_test_profile(days=3))
    menu = annotate_cooking_metadata(build_valid_menu_dict(days=3), strategy)
    saved_id = asyncio.run(
        StrategyService().save_active_strategy(
            user_id=42,
            strategy=strategy,
            plan_start_date=plan_start,
        )
    )
    menu["strategy_id"] = saved_id
    menu["plan_start_date"] = plan_start.isoformat()
    for category in menu.get("basket", []):
        for item in category.get("items", []):
            item["price"] = 50.0
    menu["total_cost"] = round(
        sum(50.0 for c in menu["basket"] for _ in c["items"]), 2
    )
    return saved_id, menu


def _payload(target_meal_id: str, target_type: str, day_num: int):
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


def _fake_claude(counter: list[int]):
    async def fake_call(_self, _system, _prompt, **_kwargs):
        counter.append(1)
        return json.dumps(_payload("day2_dinner", "dinner", 2), ensure_ascii=False)

    return fake_call


def _count(table: str) -> int:
    async def _run():
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
            return (await cursor.fetchone())[0]

    return asyncio.run(_run())


def test_reason_code_and_target_reach_memory(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day2_dinner",
            "reason": "Не люблю",
            "reason_code": "dislike_ingredient",
            "target_ingredient": "Гречка",
            "replacement_request_id": "req-1",
        },
    )
    assert response.status_code == 200

    async def _event_row():
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM memory_events")
            rows = await cursor.fetchall()
            await cursor.close()
            return rows

    rows = asyncio.run(_event_row())
    assert len(rows) == 1
    assert rows[0]["reason_code"] == "dislike_ingredient"
    assert rows[0]["target_value"] == "гречка"  # canonicalized/lowercased
    assert _count("preference_signals") == 1


def test_replacement_succeeds_when_memory_fails(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))

    async def failing_record(*_args, **_kwargs):
        raise RuntimeError("memory down")

    monkeypatch.setattr(main._memory_service, "record_meal_replaced", failing_record)

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day2_dinner",
            "reason_code": "faster",
        },
    )
    assert response.status_code == 200
    assert _count("memory_events") == 0


def test_no_second_claude_call_on_memory_failure(client, monkeypatch):
    strategy_id, menu = _prepare()
    counter: list[int] = []
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude(counter))

    async def failing_record(*_args, **_kwargs):
        raise RuntimeError("memory down")

    monkeypatch.setattr(main._memory_service, "record_meal_replaced", failing_record)

    client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day2_dinner",
            "reason_code": "faster",
        },
    )
    assert len(counter) == 1


def test_strategy_snapshot_unchanged_by_memory(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))
    before = _count("weekly_strategies")

    client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day2_dinner",
            "reason_code": "dislike_ingredient",
            "target_ingredient": "гречка",
            "replacement_request_id": "req-x",
        },
    )
    assert _count("weekly_strategies") == before


def test_no_duplicate_event_on_retry(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))

    body = {
        "strategy_id": strategy_id,
        "menu_plan": menu,
        "meal_id": "day2_dinner",
        "reason_code": "dislike_ingredient",
        "target_ingredient": "гречка",
        "replacement_request_id": "retry-key",
    }
    assert client.post("/api/menu/replace-meal", json=body).status_code == 200
    assert client.post("/api/menu/replace-meal", json=body).status_code == 200
    assert _count("memory_events") == 1


def test_legacy_request_without_reason_code_still_works(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day2_dinner",
            "reason": "Просто так",
        },
    )
    assert response.status_code == 200
    # Event recorded (meal_replaced) but no signal since reason_code is absent.
    assert _count("memory_events") == 1
    assert _count("preference_signals") == 0


def test_unknown_reason_code_returns_422(client):
    strategy_id, menu = _prepare()
    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day2_dinner",
            "reason_code": "totally_invalid",
        },
    )
    assert response.status_code == 422
