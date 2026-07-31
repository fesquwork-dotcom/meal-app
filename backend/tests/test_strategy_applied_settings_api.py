"""Tests for applied settings in strategy API (Sprint 5.23)."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from strategy.applied_cooking import AppliedCookingPreference
from strategy.builder import StrategyBuilder
from strategy.repository import StrategyRepository
from tests.strategy_fixtures import build_test_profile


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "applied-settings-api.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _save_strategy_with_applied(user_id: int = 42) -> str:
    repository = StrategyRepository()
    strategy = StrategyBuilder().build(build_test_profile())
    applied = AppliedCookingPreference(
        prefer_faster_meals=True,
        source="memory",
        profile_value=None,
    )
    return asyncio.run(
        repository.save_active(
            user_id=user_id,
            strategy=strategy,
            plan_start_date=date.today(),
            applied_cooking_preference=applied,
        )
    )


def test_active_strategy_returns_applied_settings(client):
    strategy_id = _save_strategy_with_applied()
    response = client.get("/api/strategy/current")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["strategy_id"] == strategy_id
    cooking = body["applied_settings"]["cooking"]
    assert cooking["prefer_faster_meals"] is True
    assert cooking["preference_source"] == "memory"
    assert cooking["cooking_time_limit"] == body["strategy"]["cooking_time_limit"]


def test_strategy_by_id_returns_applied_settings(client):
    strategy_id = _save_strategy_with_applied()
    response = client.get(f"/api/strategy/{strategy_id}")
    assert response.status_code == 200
    cooking = response.json()["applied_settings"]["cooking"]
    assert cooking["preference_source"] == "memory"


def test_no_strategy_has_no_applied_settings(client):
    response = client.get("/api/strategy/current")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "none"
    assert "applied_settings" not in body or body.get("applied_settings") is None
