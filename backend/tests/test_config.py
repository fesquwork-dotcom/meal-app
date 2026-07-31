import pytest

import config
from main import app
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    return TestClient(app)


def test_is_claude_configured_matches_readiness(client, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "shared-key")
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)

    async def ready_db():
        return True

    monkeypatch.setattr("main.database.check_database_ready", ready_db)

    assert config.is_claude_configured() is True

    response = client.get("/api/ready")
    assert response.status_code == 200
    assert response.json()["claude_configured"] is True


def test_deprecated_claude_api_key_fallback(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("CLAUDE_API_KEY", "legacy-key")

    assert config._resolve_anthropic_api_key() == "legacy-key"


def test_anthropic_api_key_takes_priority_over_deprecated(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "primary-key")
    monkeypatch.setenv("CLAUDE_API_KEY", "legacy-key")

    assert config._resolve_anthropic_api_key() == "primary-key"
