import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from claude_exceptions import (
    ClaudeJsonError,
    ClaudeTimeoutError,
    ClaudeUnavailableError,
    ClaudeValidationError,
    MenuConstraintError,
)
from main import app
from tests.menu_fixtures import build_valid_menu_dict
from tests.profile_test_helpers import generate_with_token, issue_preview_token, save_profile


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "generate-menu-api.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _configure_auth(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


def test_valid_plan_returns_200(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client, plan_start_date="2026-07-13")

    async def fake_generate_menu(**_kwargs):
        return build_valid_menu_dict(days=3)

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = generate_with_token(client, token)
    assert response.status_code == 200
    body = response.json()
    assert "days_plan" in body
    assert body.get("strategy_id")


def test_missing_token_returns_428(client):
    response = client.post("/api/generate-menu", json={})
    assert response.status_code == 428
    assert response.json()["code"] == "STRATEGY_PREVIEW_REQUIRED"


def test_legacy_fields_rejected(client):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)
    response = client.post(
        "/api/generate-menu",
        json={"preview_token": token, "days": 3, "budget": 3000},
    )
    assert response.status_code == 422


def test_invalid_json_returns_502(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    async def fake_generate_menu(**_kwargs):
        raise ClaudeJsonError("bad json")

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = generate_with_token(client, token)
    assert response.status_code == 502
    assert response.json()["message"] == main.USER_MESSAGE_INVALID_MENU


def test_schema_invalid_returns_502(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    async def fake_generate_menu(**_kwargs):
        raise ClaudeValidationError("schema invalid")

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = generate_with_token(client, token)
    assert response.status_code == 502


def test_constraint_invalid_returns_502(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    async def fake_generate_menu(**_kwargs):
        raise MenuConstraintError("constraints", issue_codes=["BUDGET_EXCEEDED"])

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = generate_with_token(client, token)
    assert response.status_code == 502


def test_timeout_returns_504(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    async def fake_generate_menu(**_kwargs):
        raise ClaudeTimeoutError("timeout")

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = generate_with_token(client, token)
    assert response.status_code == 504
    assert response.json()["message"] == main.USER_MESSAGE_TIMEOUT


def test_claude_unavailable_returns_503(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    async def fake_generate_menu(**_kwargs):
        raise ClaudeUnavailableError("down")

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = generate_with_token(client, token)
    assert response.status_code == 503
    assert response.json()["message"] == main.USER_MESSAGE_UNAVAILABLE


def test_user_id_still_from_telegram_auth(client, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)

    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)
    captured: list[int] = []

    async def fake_generate_menu(**kwargs):
        captured.append(kwargs.get("user_id"))
        return build_valid_menu_dict(days=1)

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = generate_with_token(client, token)
    assert response.status_code == 200
    assert captured == [99]
