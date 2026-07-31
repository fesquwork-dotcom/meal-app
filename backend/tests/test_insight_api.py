"""API contract for GET /api/insights/summary."""

import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "insights.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())


@pytest.fixture
def client():
    return TestClient(main.app)


def test_empty_history_returns_five_insufficient_insights(client):
    response = client.get("/api/insights/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["generated_at"]
    assert len(body["insights"]) == 5
    assert all(item["status"] == "insufficient_data" for item in body["insights"])
    assert all(item["confidence"]["level"] == "low" for item in body["insights"])


def test_response_is_deterministic_except_injected_timestamp(client, monkeypatch):
    monkeypatch.setattr(
        "insights.service._utc_now_iso",
        lambda: "2026-07-15T12:00:00+00:00",
    )
    first = client.get("/api/insights/summary").json()
    second = client.get("/api/insights/summary").json()
    assert first == second


def test_endpoint_requires_auth(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    response = TestClient(main.app).get("/api/insights/summary")
    assert response.status_code == 401


def test_unknown_query_data_cannot_inject_insights(client):
    baseline = client.get("/api/insights/summary").json()
    injected = client.get(
        "/api/insights/summary",
        params={
            "status": "confirmed",
            "summary": "Вы стали здоровее.",
            "strategy_id": "foreign",
        },
    ).json()
    assert injected["insights"] == baseline["insights"]

