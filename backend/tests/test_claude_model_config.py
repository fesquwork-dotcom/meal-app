"""CLAUDE_MODEL configuration: env override and Anthropic request payload."""

from __future__ import annotations

import asyncio
import json
import logging

import httpx
import pytest

import claude_service
import config
from claude_exceptions import ClaudeUnavailableError
from startup_validation import StartupConfigurationError, validate_startup_configuration


def test_default_claude_model_is_supported_sonnet():
    """Runtime default must not use retired 3.5 / Sonnet-4 dated IDs."""
    assert config.CLAUDE_MODEL
    assert "claude-3-5-sonnet-20241022" not in config.CLAUDE_MODEL
    assert "claude-sonnet-4-20250514" not in config.CLAUDE_MODEL
    # Fresh import default (module already loaded from env); check constant name.
    assert config._DEFAULT_CLAUDE_MODEL == "claude-sonnet-4-6"


def test_production_rejects_empty_claude_model(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    monkeypatch.setattr(config, "MEAL_GENERATION_ENGINE", "legacy_claude")
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOWED_ORIGINS", ["https://mealapp.ru"])
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    monkeypatch.setattr(config, "STRATEGY_PREVIEW_SECRET", "preview-secret")
    monkeypatch.setattr(config, "CLAUDE_MODEL", "")
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "app.db"))

    with pytest.raises(StartupConfigurationError, match="CLAUDE_MODEL"):
        validate_startup_configuration()


def test_generate_menu_sends_configured_claude_model(monkeypatch):
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 404
        headers = httpx.Headers({"request-id": "req_model_404"})
        text = json.dumps(
            {
                "type": "error",
                "error": {
                    "type": "not_found_error",
                    "message": "model: custom-model-from-env",
                },
            }
        )
        content = text.encode()

        def json(self):
            return json.loads(self.text)

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, url, *, headers=None, json=None):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("anthropic_http.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key-not-a-secret")
    monkeypatch.setattr(config, "CLAUDE_MODEL", "custom-model-from-env")

    with pytest.raises(ClaudeUnavailableError):
        asyncio.run(
            claude_service.generate_menu(
                budget=5000,
                days=1,
                meal_types=["breakfast", "lunch", "dinner"],
                meals_per_day=3,
                persons=2,
                proteins=["chicken"],
                goal="home",
                cooktime="fast",
                allergies=[],
            )
        )

    assert captured["json"]["model"] == "custom-model-from-env"
    assert "claude-3-5-sonnet-20241022" not in str(captured["json"])


def test_not_found_model_logs_configured_model_and_provider_ids(monkeypatch, caplog):
    class FakeResponse:
        status_code = 404
        headers = httpx.Headers({"request-id": "req_nf_99"})
        text = json.dumps(
            {
                "type": "error",
                "error": {
                    "type": "not_found_error",
                    "message": "model: claude-3-5-sonnet-20241022",
                },
            }
        )
        content = text.encode()

        def json(self):
            return json.loads(self.text)

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr("anthropic_http.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "SECRET_KEY_MUST_NOT_APPEAR")
    monkeypatch.setattr(config, "CLAUDE_MODEL", "claude-sonnet-4-6")

    with caplog.at_level(logging.ERROR):
        with pytest.raises(ClaudeUnavailableError):
            asyncio.run(
                claude_service.generate_menu(
                    budget=5000,
                    days=1,
                    meal_types=["breakfast", "lunch", "dinner"],
                    meals_per_day=3,
                    persons=2,
                    proteins=["chicken"],
                    goal="home",
                    cooktime="fast",
                    allergies=[],
                )
            )

    text = caplog.text
    assert "generation_failed" in text
    assert "configured_model=claude-sonnet-4-6" in text
    assert "provider_error_type=not_found_error" in text
    assert "provider_request_id=req_nf_99" in text
    assert "request_id=" in text
    assert "SECRET_KEY_MUST_NOT_APPEAR" not in text
    assert "ANTHROPIC_API_KEY" not in text
