import pytest
from fastapi.testclient import TestClient

import config
from main import app
from tests.telegram_hmac_reference import (
    REFERENCE_BOT_TOKEN,
    REFERENCE_USER,
    build_reference_init_data_signed_at,
)

TEST_USER = {"id": 777, "first_name": "Bob", "username": "bob"}


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _configure_auth(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", REFERENCE_BOT_TOKEN)
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


def _auth_header(user: dict | None = None) -> dict[str, str]:
    import time

    init_data = build_reference_init_data_signed_at(
        REFERENCE_BOT_TOKEN,
        str(int(time.time())),
        user or TEST_USER,
    )
    return {"Authorization": f"tma {init_data}"}


def test_get_profile_without_auth_returns_401(client):
    response = client.get("/api/profile")
    assert response.status_code == 401
    assert response.json()["message"] == "Telegram authentication failed"


def test_get_profile_malformed_scheme_returns_401(client):
    response = client.get(
        "/api/profile",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 401


def test_get_profile_with_valid_init_data_uses_telegram_user_id(client, monkeypatch):
    async def fake_get_profile(user_id: int):
        return {
            "user_id": user_id,
            "first_name": "Saved",
            "budget": 1000,
            "days": 3,
            "persons": 1,
            "proteins": ["any"],
            "goal": "home",
            "cooktime": "medium",
            "allergies": "нет",
            "store": "any",
            "updated_at": None,
            "revision": 1,
        }

    monkeypatch.setattr("main.database.get_profile", fake_get_profile)

    response = client.get("/api/profile", headers=_auth_header())
    assert response.status_code == 200
    assert response.json()["profile"]["user_id"] == 777


def test_dev_fallback_only_when_allow_dev_auth(client, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)

    response = client.get("/api/profile")
    assert response.status_code == 401

    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)

    async def fake_get_profile(user_id: int):
        return None

    monkeypatch.setattr("main.database.get_profile", fake_get_profile)

    response = client.get("/api/profile")
    assert response.status_code == 200
    assert response.json()["profile"]["user_id"] == 99


def test_health_is_public_and_safe(client):
    response = client.get("/api/health")
    assert response.status_code == 200

    body = response.json()
    assert body["status"] == "ok"
    assert body["auth_mode"] in {"telegram", "development"}
    assert isinstance(body["telegram_auth_configured"], bool)
    assert "token" not in body
    assert "TELEGRAM_BOT_TOKEN" not in str(body)


def test_generate_menu_without_auth_returns_401(client):
    response = client.post(
        "/api/generate-menu",
        json={"preview_token": "token"},
    )
    assert response.status_code == 401


def test_missing_bot_token_returns_service_unavailable(client, monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)

    response = client.get("/api/profile", headers=_auth_header())

    assert response.status_code == 503
    assert response.json()["message"] == "Service temporarily unavailable"
