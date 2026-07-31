"""API contract for durable MenuPlan: generation persistence and reads."""

import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from tests.menu_fixtures import build_valid_menu_dict
from tests.profile_test_helpers import generate_with_token, issue_preview_token, save_profile


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "menu-plan-api.db"))
    asyncio.run(database.init_db())


@pytest.fixture(autouse=True)
def _configure_auth(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


@pytest.fixture
def client():
    return TestClient(main.app)


def _generate(client, monkeypatch) -> dict:
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client, plan_start_date="2026-07-13")

    async def fake_generate_menu(**_kwargs):
        return build_valid_menu_dict(days=3)

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    response = generate_with_token(client, token)
    assert response.status_code == 200
    return response.json()


def test_generation_returns_durable_identity(client, monkeypatch):
    body = _generate(client, monkeypatch)
    assert body["menu_plan_id"]
    assert body["menu_plan_revision"] == 1
    assert body["strategy_id"]


def test_current_returns_latest_plan(client, monkeypatch):
    generated = _generate(client, monkeypatch)

    response = client.get("/api/menu/current")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["menu_plan_id"] == generated["menu_plan_id"]
    assert body["revision"] == 1
    assert body["strategy_id"] == generated["strategy_id"]
    assert body["plan"]["strategy_id"] == generated["strategy_id"]
    assert body["plan"]["days_plan"]
    assert "user_id" not in body
    assert "user_id" not in body["plan"]


def test_current_without_plan_returns_none_status(client):
    response = client.get("/api/menu/current")
    assert response.status_code == 200
    assert response.json() == {"status": "none"}


def test_get_by_id_returns_plan(client, monkeypatch):
    generated = _generate(client, monkeypatch)
    response = client.get(f"/api/menu/{generated['menu_plan_id']}")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["menu_plan_id"] == generated["menu_plan_id"]


def test_get_by_id_enforces_ownership(client, monkeypatch):
    generated = _generate(client, monkeypatch)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)
    response = client.get(f"/api/menu/{generated['menu_plan_id']}")
    assert response.status_code == 404
    assert response.json()["code"] == "MENU_PLAN_NOT_FOUND"


def test_get_unknown_id_returns_404(client):
    response = client.get("/api/menu/does-not-exist")
    assert response.status_code == 404
    assert response.json()["code"] == "MENU_PLAN_NOT_FOUND"


def test_second_generation_supersedes_first(client, monkeypatch):
    first = _generate(client, monkeypatch)
    token = issue_preview_token(client, plan_start_date="2026-07-20")

    async def fake_generate_menu(**_kwargs):
        return build_valid_menu_dict(days=3)

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    second_response = generate_with_token(client, token)
    assert second_response.status_code == 200
    second = second_response.json()
    assert second["menu_plan_id"] != first["menu_plan_id"]

    current = client.get("/api/menu/current").json()
    assert current["menu_plan_id"] == second["menu_plan_id"]

    previous = client.get(f"/api/menu/{first['menu_plan_id']}").json()
    assert previous["plan_status"] == "superseded"


def test_endpoints_require_auth(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    client = TestClient(main.app)
    assert client.get("/api/menu/current").status_code == 401
    assert client.get("/api/menu/some-id").status_code == 401
