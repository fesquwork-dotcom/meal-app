"""Ready preview exposes compact explanations and hides DecisionTrace."""

import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from tests.profile_test_helpers import preview_strategy, save_profile


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "preview-explanation.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def test_ready_preview_returns_compact_decision_explanations(client):
    save_profile(client, expected_revision=0)
    response = preview_strategy(client, plan_start_date="2026-07-20")
    body = response.json()
    assert response.status_code == 200
    assert body["status"] == "ready"
    assert body["decision_explanations"]["source"] == "trace"
    assert 1 <= len(body["decision_explanations"]["explanations"]) <= 3


def test_preview_never_returns_trace_or_codes(client):
    save_profile(client, expected_revision=0)
    response = preview_strategy(client, plan_start_date="2026-07-20")
    raw = response.text
    assert "decision_trace" not in raw
    assert "rule_code" not in raw
    assert "reason_code" not in raw
    assert "input_summary" not in raw
