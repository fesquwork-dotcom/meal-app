"""Legacy preview and generation policy tests."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from tests.profile_test_helpers import generate_with_token, issue_preview_token, save_profile


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _configure_auth_and_db(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy-policy.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


def test_no_token_generation_returns_428(client):
    response = client.post(
        "/api/generate-menu",
        json={"days": 3, "budget": 3000, "proteins": ["any"]},
    )
    assert response.status_code == 422


def test_empty_generate_body_returns_428(client):
    response = client.post("/api/generate-menu", json={})
    assert response.status_code == 428
    assert response.json()["code"] == "STRATEGY_PREVIEW_REQUIRED"


def test_token_generation_works(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    async def fake_generate_menu(**kwargs):
        from tests.menu_fixtures import build_valid_menu_dict

        menu = build_valid_menu_dict(days=kwargs["days"])
        menu["plan_start_date"] = kwargs["plan_start_date"].isoformat()
        return menu

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    response = generate_with_token(client, token)
    assert response.status_code == 200


def test_legacy_get_profile_returns_404(client):
    response = client.post("/api/get-profile", json={})
    assert response.status_code == 404


def test_canonical_get_profile_works(client):
    response = client.get("/api/profile")
    assert response.status_code == 200
    assert "revision" in response.json()
