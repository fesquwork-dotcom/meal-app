import importlib

import pytest
from fastapi.testclient import TestClient

import config
from main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_ready_returns_ready_with_valid_config(client, monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "key")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)

    async def ready_db():
        return True

    monkeypatch.setattr("main.database.check_database_ready", ready_db)

    response = client.get("/api/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["database"] is True
    assert body["telegram_auth"] is True
    assert body["claude_configured"] is True
    assert body["components"]["menu_generation"] == "ready"


def test_ready_returns_degraded_without_claude(client, monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)

    async def ready_db():
        return True

    monkeypatch.setattr("main.database.check_database_ready", ready_db)

    response = client.get("/api/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["components"]["database"] == "ready"
    assert body["components"]["menu_generation"] == "not_configured"


def test_ready_returns_503_when_db_unavailable(client, monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "key")

    async def failing_db():
        return False

    monkeypatch.setattr("main.database.check_database_ready", failing_db)

    response = client.get("/api/ready")
    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    assert response.json()["database"] is False


def test_health_does_not_expose_secrets(client):
    response = client.get("/api/health")
    body = response.json()

    assert "token" not in body
    assert "ANTHROPIC_API_KEY" not in str(body)


def test_production_module_has_no_test_signing_helper():
    module = importlib.import_module("telegram_auth")
    assert not hasattr(module, "build_signed_init_data")
