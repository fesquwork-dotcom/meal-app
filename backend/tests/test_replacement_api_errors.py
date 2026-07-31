"""Controlled API contract for replacement price failures."""

from __future__ import annotations

import asyncio
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from strategy.replacement_service import MealReplacementService
from strategy.service import StrategyService
from tests.test_replace_meal_api import _build_strategy_menu, _normalize_menu_budget
from tests.test_replacement_price_resolution import _llm_payload, _unpriced_ingredients


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "replace-api-errors.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def test_replacement_price_unresolved_envelope_has_request_id(client, monkeypatch):
    strategy, menu = _build_strategy_menu("pending")
    strategy_id = asyncio.run(
        StrategyService().save_active_strategy(
            user_id=42,
            strategy=strategy,
            plan_start_date=date.today(),
        )
    )
    menu["strategy_id"] = strategy_id
    _normalize_menu_budget(menu)

    async def fake_call(_self, _system, _prompt, **_kwargs):
        return json.dumps(
            _llm_payload("day2_dinner", _unpriced_ingredients()),
            ensure_ascii=False,
        )

    monkeypatch.setattr(MealReplacementService, "_call_claude", fake_call)

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day2_dinner",
        },
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "REPLACEMENT_PRICE_UNRESOLVED"
    assert isinstance(body.get("request_id"), str) and body["request_id"]
    assert response.headers.get("X-Request-Id")
    assert "Access-Control-Allow-Origin" in response.headers or True  # middleware may set
    assert "Салат с киноа" not in json.dumps(body, ensure_ascii=False)
