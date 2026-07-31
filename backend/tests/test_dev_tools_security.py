"""Sprint 9.5 — production guards for development QA tools."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from startup_validation import StartupConfigurationError, validate_startup_configuration


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "dev-sec.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    asyncio.run(database.init_db())
    return TestClient(main.app)


def test_production_plus_dev_auth_fails_startup(monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "key")
    monkeypatch.setattr(config, "STRATEGY_PREVIEW_SECRET", "secret")
    monkeypatch.setattr(config, "ALLOWED_ORIGINS", ["https://example.com"])
    with pytest.raises(StartupConfigurationError) as exc:
        validate_startup_configuration()
    assert "ALLOW_DEV_AUTH" in str(exc.value)


def test_dev_endpoints_disabled_when_environment_production(client, monkeypatch):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    # Guard helper must still refuse tools in production label.
    response = client.post(
        "/api/dev/reset-current-user",
        json={"confirm": "RESET", "mode": "history_only"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "DEV_TOOLS_DISABLED"


def test_dev_endpoints_disabled_without_dev_auth(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "no-dev.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "key")
    monkeypatch.setattr(config, "STRATEGY_PREVIEW_SECRET", "secret")
    asyncio.run(database.init_db())
    client = TestClient(main.app)
    # No Authorization header and ALLOW_DEV_AUTH=false → 401 before tools run.
    response = client.post(
        "/api/dev/load-qa-scenario",
        json={"scenario": "fresh_user"},
    )
    assert response.status_code == 401
