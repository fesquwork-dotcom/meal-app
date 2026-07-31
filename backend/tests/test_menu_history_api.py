"""Sprint 7.3 — paginated menu history and original snapshot API."""

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
from tests.menu_fixtures import build_valid_menu_dict
from tests.strategy_fixtures import build_test_profile


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "menu-history.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())


@pytest.fixture
def client():
    return TestClient(main.app)


def _save_plan(menu_plan_id: str, *, user_id: int = 42, summary: str = "План") -> str:
    strategy = StrategyBuilder().build(build_test_profile(days=3))
    menu = build_valid_menu_dict(days=3)
    menu["summary"] = summary
    menu["plan_start_date"] = "2026-07-13"
    return asyncio.run(
        StrategyRepository().save_active(
            user_id=user_id,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
            menu_plan_id=menu_plan_id,
            menu_plan_json=json.dumps(menu, ensure_ascii=False),
        )
    )


def _save_many(count: int) -> list[str]:
    ids = [f"plan-{index}" for index in range(1, count + 1)]
    for index, menu_plan_id in enumerate(ids, start=1):
        _save_plan(menu_plan_id, summary=f"План {index}")
        # Distinct created_at ordering is not guaranteed within a second;
        # make it deterministic for pagination tests.
        asyncio.run(_shift_created_at(menu_plan_id, index))
    return ids


async def _shift_created_at(menu_plan_id: str, index: int) -> None:
    async with aiosqlite.connect(database.resolve_database_path()) as db:
        await db.execute(
            "UPDATE menu_plans SET created_at = ? WHERE id = ?",
            (f"2026-07-{index:02d}T10:00:00+00:00", menu_plan_id),
        )
        await db.commit()


def test_history_returns_compact_summaries_without_plan_json(client):
    _save_many(3)
    response = client.get("/api/menu/history")
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 3
    assert body["next_cursor"] is None

    newest = body["items"][0]
    assert newest["menu_plan_id"] == "plan-3"
    assert newest["plan_status"] == "active"
    assert newest["days"] == 3
    assert newest["summary"] == "План 3"
    assert newest["has_replacements"] is False
    # Compact contract: no full plan payload in the list.
    for item in body["items"]:
        assert "plan" not in item
        assert "days_plan" not in item
        assert "recipes" not in item
        assert "basket" not in item
        assert "user_id" not in item

    # Older generations are superseded.
    assert body["items"][1]["plan_status"] == "superseded"
    assert body["items"][2]["plan_status"] == "superseded"


def test_history_pagination_with_cursor(client):
    _save_many(5)
    first_page = client.get("/api/menu/history", params={"limit": 2}).json()
    assert [item["menu_plan_id"] for item in first_page["items"]] == [
        "plan-5",
        "plan-4",
    ]
    assert first_page["next_cursor"]

    second_page = client.get(
        "/api/menu/history",
        params={"limit": 2, "cursor": first_page["next_cursor"]},
    ).json()
    assert [item["menu_plan_id"] for item in second_page["items"]] == [
        "plan-3",
        "plan-2",
    ]

    third_page = client.get(
        "/api/menu/history",
        params={"limit": 2, "cursor": second_page["next_cursor"]},
    ).json()
    assert [item["menu_plan_id"] for item in third_page["items"]] == ["plan-1"]
    assert third_page["next_cursor"] is None


def test_history_malformed_cursor_returns_422(client):
    response = client.get("/api/menu/history", params={"cursor": "garbage"})
    assert response.status_code == 422
    assert response.json()["code"] == "REQUEST_VALIDATION_ERROR"


def test_history_is_scoped_to_user(client, monkeypatch):
    _save_many(2)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)
    body = client.get("/api/menu/history").json()
    assert body["items"] == []
    assert body["next_cursor"] is None


def test_history_limit_is_capped(client):
    _save_many(2)
    response = client.get("/api/menu/history", params={"limit": 9999})
    assert response.status_code == 200
    assert len(response.json()["items"]) == 2


def test_original_endpoint_returns_immutable_snapshot(client):
    _save_plan("plan-1")
    repository = MenuPlanRepository()
    changed = build_valid_menu_dict(days=3)
    changed["summary"] = "После замены"
    asyncio.run(
        repository.append_revision(
            menu_plan_id="plan-1",
            user_id=42,
            expected_revision=1,
            plan_json=json.dumps(changed, ensure_ascii=False),
            change_type=MenuPlanChangeType.MEAL_REPLACEMENT,
        )
    )

    current = client.get("/api/menu/plan-1").json()
    assert current["view"] == "current"
    assert current["revision"] == 2
    assert current["has_replacements"] is True
    assert current["plan"]["summary"] == "После замены"

    original = client.get("/api/menu/plan-1/original").json()
    assert original["view"] == "original"
    assert original["revision"] == 1
    assert original["has_replacements"] is True
    assert original["plan"]["summary"] == "План"
    assert original["strategy_id"] == current["strategy_id"]


def test_original_endpoint_enforces_ownership(client, monkeypatch):
    _save_plan("plan-1")
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)
    response = client.get("/api/menu/plan-1/original")
    assert response.status_code == 404
    assert response.json()["code"] == "MENU_PLAN_NOT_FOUND"


def test_history_survives_malformed_plan_json(client):
    _save_plan("plan-1")

    async def corrupt():
        async with aiosqlite.connect(database.resolve_database_path()) as db:
            await db.execute(
                "UPDATE menu_plan_revisions SET plan_json = '{broken' "
                "WHERE menu_plan_id = 'plan-1'"
            )
            await db.commit()

    asyncio.run(corrupt())
    body = client.get("/api/menu/history").json()
    assert len(body["items"]) == 1
    item = body["items"][0]
    assert item["menu_plan_id"] == "plan-1"
    assert item["days"] is None
    assert item["total_cost"] is None
    assert item["summary"] is None


def test_history_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    client = TestClient(main.app)
    assert client.get("/api/menu/history").status_code == 401
    assert client.get("/api/menu/plan-1/original").status_code == 401
