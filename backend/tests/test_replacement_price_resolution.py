"""Replacement basket price resolution — domain error, correction, privacy."""

from __future__ import annotations

import asyncio
import json
import logging
from copy import deepcopy
from datetime import date

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from shopping.exceptions import BasketPriceUnavailableError
from strategy.replacement_exceptions import ReplacementPriceResolutionError
from strategy.replacement_merge import merge_replacement
from strategy.replacement_models import MealReplacementItem, ReplacementLLMResponse
from strategy.replacement_prompt import (
    PRICE_UNRESOLVED_CORRECTION_RULE,
    build_replacement_correction_prompt,
    collect_resolvable_product_labels,
)
from strategy.replacement_service import MealReplacementService
from strategy.service import StrategyService
from tests.test_replacement_merge_recipe_id import _context
from tests.test_replace_meal_api import _build_strategy_menu, _normalize_menu_budget


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "replace-price.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _llm_payload(target_id: str, ingredients: list[dict]) -> dict:
    return {
        "replacement": {
            "meal": {
                "type": "dinner",
                "recipe_name": "Салат с киноа",
                "meal_id": target_id,
                "requires_cooking": True,
                "prepared_on_day": 2,
                "uses_leftovers": False,
                "source_meal_id": None,
            },
            "recipe": {
                "name": "Салат с киноа",
                "emoji": "🥗",
                "cook_time": "25 мин",
                "kbju": "Б:15г Ж:10г У:40г",
                "ingredients": ingredients,
                "steps": ["Смешать", "Подать"],
            },
        },
        "affected_meals": [],
    }


def _priced_ingredients() -> list[dict]:
    return [
        {"name": "творог", "amount": "300 г", "contribution": "purchase"},
        {"name": "яйца", "amount": "2 шт", "contribution": "purchase"},
    ]


def _unpriced_ingredients() -> list[dict]:
    return [
        {"name": "Киноа", "amount": "150 г", "contribution": "purchase"},
        {"name": "Нут консервированный", "amount": "200 г", "contribution": "purchase"},
        {"name": "Помидоры черри", "amount": "150 г", "contribution": "purchase"},
        {"name": "Авокадо", "amount": "1 шт", "contribution": "purchase"},
        {"name": "Красный лук", "amount": "50 г", "contribution": "purchase"},
        {"name": "Тахини паста", "amount": "30 г", "contribution": "purchase"},
        {"name": "Лимон", "amount": "1 шт", "contribution": "purchase"},
    ]


def test_merge_raises_domain_error_not_value_error():
    from menu_models import DayMeal, Recipe, RecipeIngredient
    from tests.test_replacement_merge_recipe_id import _simple_menu

    plan = _simple_menu()
    llm = ReplacementLLMResponse(
        replacement=MealReplacementItem(
            meal=DayMeal(
                type="dinner",
                recipe_name="Салат",
                meal_id="day1_dinner",
                requires_cooking=True,
                prepared_on_day=1,
            ),
            recipe=Recipe(
                name="Салат",
                recipe_id="recipe_day1_dinner",
                ingredients=[
                    RecipeIngredient(name=item["name"], amount=item["amount"])
                    for item in _unpriced_ingredients()
                ],
                steps=["Смешать"],
            ),
        )
    )
    try:
        merge_replacement(_context(plan), llm)
        pytest.fail("expected ReplacementPriceResolutionError")
    except ReplacementPriceResolutionError as exc:
        assert len(exc.unresolved_items) >= 1
        assert exc.code == "REPLACEMENT_PRICE_UNRESOLVED"
    except ValueError as exc:
        pytest.fail(f"ValueError leaked: {exc}")


def test_collect_resolvable_includes_basket_and_fallbacks():
    strategy, menu = _build_strategy_menu("pending")
    _normalize_menu_budget(menu)
    from menu_models import MenuPlan

    plan = MenuPlan.model_validate(menu)
    labels = collect_resolvable_product_labels(plan.basket)
    assert labels
    assert any("яйц" in label.lower() or "творог" in label.lower() or "рис" in label.lower() for label in labels)


def test_correction_prompt_includes_price_rule_and_safe_names():
    strategy, menu = _build_strategy_menu("pending")
    _normalize_menu_budget(menu)
    from menu_models import MenuPlan

    plan = MenuPlan.model_validate(menu)
    context = _context(plan)
    prompt = build_replacement_correction_prompt(
        ["REPLACEMENT_PRICE_UNRESOLVED"],
        ["price gap"],
        context,
        "day2_dinner",
        unresolved_items=["Киноа", "Тахини паста"],
    )
    assert "REPLACEMENT_PRICE_UNRESOLVED" in prompt
    assert PRICE_UNRESOLVED_CORRECTION_RULE.split("\n")[0] in prompt
    assert "Киноа" in prompt
    assert "Тахини паста" in prompt
    assert "доступн" in prompt.lower()


def test_api_returns_422_not_500_when_prices_unresolved(client, monkeypatch):
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
    target_id = "day2_dinner"
    original_dinner = deepcopy(menu["days_plan"][1]["meals"])
    original_basket = deepcopy(menu["basket"])
    original_total = menu["total_cost"]

    async def fake_call(_self, _system, _prompt, **_kwargs):
        return json.dumps(
            _llm_payload(target_id, _unpriced_ingredients()),
            ensure_ascii=False,
        )

    monkeypatch.setattr(MealReplacementService, "_call_claude", fake_call)

    response = client.post(
        "/api/menu/replace-meal",
        json={
            "strategy_id": strategy_id,
            "menu_plan": menu,
            "meal_id": target_id,
            "reason": "Хочу другое",
        },
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "REPLACEMENT_PRICE_UNRESOLVED"
    assert "стоимость" in body["message"].lower()
    assert "не изменён" in body["message"].lower()
    assert "Киноа" not in json.dumps(body, ensure_ascii=False)
    assert "traceback" not in json.dumps(body).lower()
    assert body["details"]["unresolved_count"] >= 1

    # Request body is the source of truth for client state; server must not
    # have mutated durable storage either (covered in atomicity test).
    assert menu["days_plan"][1]["meals"] == original_dinner
    assert menu["basket"] == original_basket
    assert menu["total_cost"] == original_total


def test_correction_retry_then_success(client, monkeypatch):
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
    target_id = "day2_dinner"
    calls: list[str] = []

    async def fake_call(_self, _system, prompt, **_kwargs):
        calls.append(prompt)
        if len(calls) == 1:
            return json.dumps(
                _llm_payload(target_id, _unpriced_ingredients()),
                ensure_ascii=False,
            )
        return json.dumps(
            _llm_payload(target_id, _priced_ingredients()),
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
    assert len(calls) == 2
    assert "REPLACEMENT_PRICE_UNRESOLVED" in calls[1]
    body = response.json()
    assert body["replaced_meal_id"] == target_id
    assert body["menu_plan"]["strategy_id"] == strategy_id


def test_retry_exhausted_keeps_single_request_id(client, monkeypatch, caplog):
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
    target_id = "day2_dinner"
    request_ids: list[str] = []

    async def fake_call(_self, _system, _prompt, *, request_id: str, **_kwargs):
        request_ids.append(request_id)
        return json.dumps(
            _llm_payload(target_id, _unpriced_ingredients()),
            ensure_ascii=False,
        )

    monkeypatch.setattr(MealReplacementService, "_call_claude", fake_call)

    with caplog.at_level(logging.WARNING):
        response = client.post(
            "/api/menu/replace-meal",
            json={
                "strategy_id": strategy_id,
                "menu_plan": menu,
                "meal_id": target_id,
            },
        )

    assert response.status_code == 422
    assert len(request_ids) == 3
    assert len(set(request_ids)) == 1
    events = [
        record.message
        for record in caplog.records
        if "replacement_price_resolution_failed" in record.message
    ]
    assert len(events) == 3
    assert all(f"request_id={request_ids[0]}" in event for event in events)


def test_logs_privacy_safe_in_production(client, monkeypatch, caplog):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
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

    with caplog.at_level(logging.WARNING):
        client.post(
            "/api/menu/replace-meal",
            json={
                "strategy_id": strategy_id,
                "menu_plan": menu,
                "meal_id": "day2_dinner",
            },
        )

    joined = "\n".join(record.message for record in caplog.records)
    assert "replacement_price_resolution_failed" in joined
    assert "Киноа" not in joined
    assert "Тахини" not in joined
    assert "unresolved_names=[]" in joined


def test_success_path_still_resolves_priced_ingredients(client, monkeypatch):
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
            _llm_payload("day2_dinner", _priced_ingredients()),
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
    )
    assert response.status_code == 200
    plan = response.json()["menu_plan"]
    assert plan["basket"]
    assert plan["total_cost"] is not None


def test_basket_price_unavailable_still_domain_typed():
    err = BasketPriceUnavailableError(["Киноа", "Лимон"])
    wrapped = ReplacementPriceResolutionError(err.unresolved)
    assert wrapped.unresolved_items == ("Киноа", "Лимон")
    assert not isinstance(wrapped, ValueError)
