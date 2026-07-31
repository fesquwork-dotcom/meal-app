"""Sprint 9.5 — diagnostics and consistency."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "diag.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    asyncio.run(database.init_db())
    return TestClient(main.app)


def test_health_privacy_and_version(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "environment" in body
    text = str(body).lower()
    assert "anthropic" not in text
    assert "secret" not in text
    assert "database_path" not in text
    assert "token" not in body


def test_ready_components_shape(client, monkeypatch):
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "")

    async def ready_db():
        return True

    monkeypatch.setattr("main.database.check_database_ready", ready_db)
    body = client.get("/api/ready").json()
    assert "components" in body
    assert body["components"]["menu_generation"] == "not_configured"
    assert body["status"] == "degraded"


def test_dev_diagnostics_consistency(client):
    body = client.get("/api/dev/diagnostics").json()
    assert body["dev_mode"] is True
    assert body["consistency"]["status"] in {"ok", "issues_found"}
    assert "lifecycle_counts" in body
    assert "scenarios" in body
    text = str(body).lower()
    assert "initdata" not in text
    assert "anthropic_api_key" not in text


def test_request_id_header_present(client):
    response = client.get("/api/health")
    assert response.headers.get("X-Request-Id", "").startswith("req_")
