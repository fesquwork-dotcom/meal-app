"""Replacement must not persist MenuPlan/Basket when price resolution fails."""

from __future__ import annotations

import asyncio
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from menu_models import MenuPlan
from menu_plan.records import MenuPlanChangeType
from menu_plan.repository import MenuPlanRepository
from strategy.builder import StrategyBuilder
from strategy.replacement_exceptions import ReplacementPriceResolutionError
from strategy.replacement_models import ReplaceMealRequest
from strategy.replacement_service import MealReplacementService
from strategy.repository import StrategyRepository
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict
from tests.strategy_fixtures import build_test_profile
from tests.test_replacement_price_resolution import _llm_payload, _unpriced_ingredients


@pytest.fixture
def db(tmp_path, monkeypatch):
    db_path = tmp_path / "replace-atomic.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())


@pytest.fixture
def client(db):
    return TestClient(main.app)


def _normalize_menu_budget(menu: dict) -> None:
    total = 0.0
    for category in menu.get("basket", []):
        for item in category.get("items", []):
            item["price"] = 50.0
            total += 50.0
    menu["total_cost"] = round(total, 2)


def _setup_durable_plan(menu_plan_id: str = "plan-price-1"):
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
    return strategy_id, menu, menu_plan_id


def test_price_failure_does_not_append_revision(client, monkeypatch):
    strategy_id, menu, menu_plan_id = _setup_durable_plan()
    original_json = json.dumps(menu, ensure_ascii=False)

    async def fake_call(_self, _system, _prompt, **_kwargs):
        return json.dumps(
            _llm_payload("day2_dinner", _unpriced_ingredients()),
            ensure_ascii=False,
        )

    monkeypatch.setattr(MealReplacementService, "_call_claude", fake_call)

    repo = MenuPlanRepository()
    before = asyncio.run(repo.get_by_id(menu_plan_id, 42))
    before_revision = asyncio.run(repo.get_revision(menu_plan_id, before.current_revision))

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": "day2_dinner",
            "menu_plan_id": menu_plan_id,
            "expected_revision": before.current_revision,
        },
    )
    assert response.status_code == 422
    assert response.json()["code"] == "REPLACEMENT_PRICE_UNRESOLVED"

    after = asyncio.run(repo.get_by_id(menu_plan_id, 42))
    assert after.current_revision == before.current_revision
    after_revision = asyncio.run(repo.get_revision(menu_plan_id, after.current_revision))
    assert after_revision.plan_json == before_revision.plan_json
    assert after.original_plan_json == before.original_plan_json
    assert "Киноа" not in after_revision.plan_json
    assert "Салат с киноа" not in after_revision.plan_json
    # Client-provided snapshot also unchanged (no partial write path).
    assert json.dumps(menu, ensure_ascii=False) == original_json


def test_price_failure_does_not_call_persist(db, monkeypatch):
    strategy_id, menu, _menu_plan_id = _setup_durable_plan("plan-price-2")
    persist_calls: list[object] = []

    async def fake_call(_self, _system, _prompt, **_kwargs):
        return json.dumps(
            _llm_payload("day2_dinner", _unpriced_ingredients()),
            ensure_ascii=False,
        )

    async def fake_persist(self, request, user_id, merged, changed_ids):
        persist_calls.append((request.meal_id, list(changed_ids)))
        return 2

    monkeypatch.setattr(MealReplacementService, "_call_claude", fake_call)
    monkeypatch.setattr(MealReplacementService, "_persist_revision", fake_persist)

    service = MealReplacementService()
    request = ReplaceMealRequest(
        strategy_id=strategy_id,
        menu_plan=MenuPlan.model_validate(menu),
        meal_id="day2_dinner",
        menu_plan_id="plan-price-2",
        expected_revision=1,
    )

    with pytest.raises(ReplacementPriceResolutionError):
        asyncio.run(service.replace_meal(request, user_id=42))

    assert persist_calls == []
    assert MenuPlanChangeType.MEAL_REPLACEMENT.value == "meal_replacement"
