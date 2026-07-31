"""Integration tests for behavior evaluation after meal replacement."""

from __future__ import annotations

import asyncio
import json

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from behavior.constants import BehaviorInsightStatus
from behavior.repository import BehaviorRepository
from strategy.builder import StrategyBuilder
from strategy.replacement_service import MealReplacementService
from strategy.service import StrategyService
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict
from tests.strategy_fixtures import build_test_profile


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "behavior-hook.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _prepare():
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
    menu["total_cost"] = round(sum(50.0 for c in menu["basket"] for _ in c["items"]), 2)
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


def test_replacement_evaluates_behavior(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))
    body = {
        "strategy_id": strategy_id,
        "menu_plan": menu,
        "meal_id": "day2_dinner",
        "reason_code": "generic",
        "replacement_request_id": "hook-1",
    }
    response = client.post("/api/menu/replace-meal", json=body)
    assert response.status_code == 200
    assert _count("memory_events") == 1
    assert _count("behavior_insights") >= 1


def test_second_replacement_can_create_candidate(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))
    base = {
        "strategy_id": strategy_id,
        "menu_plan": menu,
        "meal_id": "day2_dinner",
        "reason_code": "generic",
    }
    client.post("/api/menu/replace-meal", json={**base, "replacement_request_id": "hook-a"})
    client.post("/api/menu/replace-meal", json={**base, "replacement_request_id": "hook-b"})
    insights = client.get("/api/behavior/insights").json()
    assert insights["candidate_count"] >= 1


def test_duplicate_replacement_does_not_inflate_evidence(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))
    body = {
        "strategy_id": strategy_id,
        "menu_plan": menu,
        "meal_id": "day2_dinner",
        "reason_code": "generic",
        "replacement_request_id": "dup-hook",
    }
    assert client.post("/api/menu/replace-meal", json=body).status_code == 200
    assert client.post("/api/menu/replace-meal", json=body).status_code == 200
    assert _count("memory_events") == 1
    insights = client.get("/api/behavior/insights").json()
    if insights["insights"]:
        assert insights["insights"][0]["evidence_count"] == 1


def test_evaluation_error_does_not_fail_replacement(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))

    async def failing_eval(*_args, **_kwargs):
        raise RuntimeError("behavior down")

    monkeypatch.setattr(main._behavior_service, "evaluate_user", failing_eval)
    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day2_dinner",
            "reason_code": "generic",
            "replacement_request_id": "hook-fail",
        },
    )
    assert response.status_code == 200


def test_validation_failure_does_not_evaluate_behavior(client):
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
    assert _count("behavior_insights") == 0


def test_replacement_does_not_mutate_profile_or_strategy(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))
    before_strategies = _count("weekly_strategies")
    before_profiles = _count("profiles")
    client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day2_dinner",
            "reason_code": "generic",
            "replacement_request_id": "hook-safe",
        },
    )
    assert _count("weekly_strategies") == before_strategies
    assert _count("profiles") == before_profiles


def test_memory_failure_skips_behavior_evaluation(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))

    async def failing_record(*_args, **_kwargs):
        raise RuntimeError("memory down")

    evaluated: list[int] = []

    async def track_eval(user_id: int, **_kwargs):
        evaluated.append(user_id)

    monkeypatch.setattr(main._memory_service, "record_meal_replaced", failing_record)
    monkeypatch.setattr(main._behavior_service, "evaluate_user", track_eval)
    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day2_dinner",
            "reason_code": "generic",
            "replacement_request_id": "hook-no-memory",
        },
    )
    assert response.status_code == 200
    assert evaluated == []


def test_dismissed_insight_not_reopened_after_hook(client, monkeypatch):
    strategy_id, menu = _prepare()
    monkeypatch.setattr(MealReplacementService, "_call_claude", _fake_claude([]))
    base = {
        "strategy_id": strategy_id,
        "menu_plan": menu,
        "meal_id": "day2_dinner",
        "reason_code": "generic",
    }
    client.post("/api/menu/replace-meal", json={**base, "replacement_request_id": "d1"})
    client.post("/api/menu/replace-meal", json={**base, "replacement_request_id": "d2"})
    insight_id = client.get("/api/behavior/insights").json()["insights"][0]["id"]
    client.post(f"/api/behavior/insights/{insight_id}/dismiss")
    client.post("/api/menu/replace-meal", json={**base, "replacement_request_id": "d3"})
    record = asyncio.run(BehaviorRepository().get_by_id(42, insight_id))
    assert record.status == BehaviorInsightStatus.DISMISSED.value
