import pytest

import config
from startup_validation import StartupConfigurationError, validate_cors_origins, validate_startup_configuration


def test_production_requires_telegram_token(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(config, "ALLOWED_ORIGINS", ["https://frontend.example.com"])
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "DATABASE_PATH", "./test-app.db")

    with pytest.raises(StartupConfigurationError, match="TELEGRAM_BOT_TOKEN"):
        validate_startup_configuration()


def test_production_requires_claude_key(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOWED_ORIGINS", ["https://frontend.example.com"])
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "app.db"))

    with pytest.raises(StartupConfigurationError, match="ANTHROPIC_API_KEY"):
        validate_startup_configuration()


def test_production_rejects_empty_allowed_origins(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOWED_ORIGINS", [])
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "app.db"))

    with pytest.raises(StartupConfigurationError, match="ALLOWED_ORIGINS"):
        validate_startup_configuration()


def test_wildcard_cors_rejected():
    with pytest.raises(StartupConfigurationError, match="Wildcard"):
        validate_cors_origins(["*"])


def test_development_allows_missing_token(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")
    monkeypatch.setattr(config, "ALLOWED_ORIGINS", ["http://localhost:5173"])
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "app.db"))

    validate_startup_configuration()
