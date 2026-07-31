"""Sprint 9.5 — QA fixture API and scenario coverage."""

from __future__ import annotations

import asyncio
import pathlib

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from dev_tools.scenarios import QA_SCENARIO_NAMES
from learned_preferences.service import LearnedPreferenceService


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "qa.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    monkeypatch.setattr(config, "ENVIRONMENT", "development")
    monkeypatch.setattr(config, "ADAPTIVE_PREFERENCES", True)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def test_unknown_scenario_rejected(client):
    response = client.post(
        "/api/dev/load-qa-scenario",
        json={"scenario": "not_a_real_scenario"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "DEV_QA_SCENARIO_UNKNOWN"


def test_fixtures_module_does_not_import_claude():
    source = (
        pathlib.Path(__file__).resolve().parents[1]
        / "dev_tools"
        / "fixtures.py"
    ).read_text(encoding="utf-8")
    assert "import claude" not in source
    assert "from claude" not in source
    assert "import anthropic" not in source
    assert "date.today()" not in source


@pytest.mark.parametrize("scenario", sorted(QA_SCENARIO_NAMES))
def test_every_allowlisted_scenario_loads(client, scenario):
    response = client.post(
        "/api/dev/load-qa-scenario",
        json={"scenario": scenario},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "ok"
    assert body["scenario"] == scenario
    assert body["anchor_date"] == "2026-07-13"


def test_ineffective_and_dismissed_review_states(client):
    client.post(
        "/api/dev/load-qa-scenario",
        json={"scenario": "learned_preference_ineffective"},
    )
    listed = client.get("/api/learned-preferences").json()["preferences"][0]
    assert listed["status"] == "active"
    assert listed["effectiveness"]["status"] == "ineffective"
    assert listed["effectiveness"]["generation"] == 1
    assert listed["last_review_generation"] is None

    client.post(
        "/api/dev/load-qa-scenario",
        json={"scenario": "review_dismissed"},
    )
    dismissed = client.get("/api/learned-preferences").json()["preferences"][0]
    assert dismissed["last_review_generation"] == 1
    assert dismissed["effectiveness"]["generation"] == 1

    client.post(
        "/api/dev/load-qa-scenario",
        json={"scenario": "review_new_generation"},
    )
    again = client.get("/api/learned-preferences").json()["preferences"][0]
    assert again["effectiveness"]["generation"] == 2
    assert again["last_review_generation"] == 1


def test_fixture_deterministic_anchor(client):
    first = client.post(
        "/api/dev/load-qa-scenario",
        json={"scenario": "learned_preference_effective"},
    ).json()
    second = client.post(
        "/api/dev/load-qa-scenario",
        json={"scenario": "learned_preference_effective"},
    ).json()
    assert first["anchor_date"] == second["anchor_date"] == "2026-07-13"
    prefs = asyncio.run(
        LearnedPreferenceService().list_preferences(42)
    )
    assert prefs.preferences
