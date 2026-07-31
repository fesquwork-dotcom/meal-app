"""API contract for GET /api/menu/{menu_plan_id}/delta."""

import asyncio
import json
from datetime import date

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from menu_plan.records import MenuPlanChangeType
from menu_plan.repository import MenuPlanRepository
from strategy.builder import StrategyBuilder
from strategy.repository import StrategyRepository
from tests.menu_fixtures import build_valid_menu_dict, clone_menu
from tests.strategy_fixtures import build_test_profile


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "plan-delta.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())


@pytest.fixture
def client():
    return TestClient(main.app)


def _save_plan(menu_plan_id: str = "plan-1") -> dict:
    strategy = StrategyBuilder().build(build_test_profile(days=3))
    menu = build_valid_menu_dict(days=3)
    menu["plan_start_date"] = "2026-07-13"
    asyncio.run(
        StrategyRepository().save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
            menu_plan_id=menu_plan_id,
            menu_plan_json=json.dumps(menu, ensure_ascii=False),
        )
    )
    return menu


def _append_cheaper_revision(menu: dict, menu_plan_id: str = "plan-1") -> None:
    changed = clone_menu(menu)
    changed["total_cost"] = float(menu["total_cost"]) - 250.0
    changed["days_plan"][1]["meals"][2]["recipe_name"] = "Новая запеканка"
    asyncio.run(
        MenuPlanRepository().append_revision(
            menu_plan_id=menu_plan_id,
            user_id=42,
            expected_revision=1,
            plan_json=json.dumps(changed, ensure_ascii=False),
            change_type=MenuPlanChangeType.MEAL_REPLACEMENT,
        )
    )


def test_delta_after_replacement(client):
    menu = _save_plan()
    _append_cheaper_revision(menu)

    response = client.get("/api/menu/plan-1/delta")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["menu_plan_id"] == "plan-1"
    assert body["revision"] == 2
    assert body["has_replacements"] is True

    metrics = {metric["id"]: metric for metric in body["delta"]["metrics"]}
    assert metrics["total_cost"]["delta"] == -250.0
    assert metrics["total_cost"]["direction"] == "decreased"
    assert metrics["changed_meals"]["delta"] == 1


def test_delta_without_replacements_is_unchanged(client):
    _save_plan()
    body = client.get("/api/menu/plan-1/delta").json()
    assert body["has_replacements"] is False
    metrics = {metric["id"]: metric for metric in body["delta"]["metrics"]}
    assert metrics["total_cost"]["delta"] == 0
    assert metrics["total_cost"]["direction"] == "unchanged"


def test_delta_enforces_ownership(client, monkeypatch):
    _save_plan()
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)
    response = client.get("/api/menu/plan-1/delta")
    assert response.status_code == 404
    assert response.json()["code"] == "MENU_PLAN_NOT_FOUND"


def test_delta_unknown_plan_returns_404(client):
    response = client.get("/api/menu/ghost/delta")
    assert response.status_code == 404


def test_delta_degrades_on_malformed_stored_json(client):
    _save_plan()

    async def corrupt():
        async with aiosqlite.connect(database.resolve_database_path()) as db:
            await db.execute(
                "UPDATE menu_plans SET original_plan_json = '{broken' WHERE id = 'plan-1'"
            )
            await db.commit()

    asyncio.run(corrupt())
    body = client.get("/api/menu/plan-1/delta").json()
    assert body == {"status": "none"}


def test_delta_payload_is_aggregate_only(client):
    menu = _save_plan()
    _append_cheaper_revision(menu)
    body = client.get("/api/menu/plan-1/delta").json()
    text = json.dumps(body, ensure_ascii=False)
    # No recipe names, ingredients, or user ids leave the delta endpoint.
    assert "Новая запеканка" not in text
    assert "Овсянка" not in text
    assert "ingredients" not in text
    assert "user_id" not in text


def test_delta_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    client = TestClient(main.app)
    assert client.get("/api/menu/plan-1/delta").status_code == 401
