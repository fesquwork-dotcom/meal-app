"""Tests for strategy compare API (Sprint 5.24)."""

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
from tests.menu_fixtures import build_valid_menu_dict
from tests.profile_test_helpers import save_profile
from tests.strategy_fixtures import build_test_profile


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "strategy-compare.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _save_strategy(user_id: int = 42, **profile_overrides) -> str:
    repository = StrategyRepository()
    profile = build_test_profile(**profile_overrides)
    strategy = StrategyBuilder().build(profile)
    applied = AppliedCookingPreference(
        prefer_faster_meals=strategy.prefer_faster_meals,
        source="default",
        profile_value=None,
    )
    return asyncio.run(
        repository.save_active(
            user_id=user_id,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
            applied_cooking_preference=applied,
        )
    )


def test_compare_returns_diff_and_preview_token(client):
    save_profile(client, expected_revision=0)
    strategy_id = _save_strategy()
    response = client.post(
        f"/api/strategy/{strategy_id}/compare",
        json={"plan_start_date": "2026-07-20"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["preview"]["preview_token"]
    assert body["diff"]["has_changes"] is False
    assert body["diff"]["comparison_quality"] in {"exact", "partial"}


def test_compare_detects_budget_change(client):
    save_profile(client, expected_revision=0, budget=5000)
    strategy_id = _save_strategy(budget=3000)
    response = client.post(
        f"/api/strategy/{strategy_id}/compare",
        json={"plan_start_date": "2026-07-20"},
    )
    assert response.status_code == 200
    diff = response.json()["diff"]
    assert diff["has_changes"] is True
    assert any(change["key"] == "budget" for change in diff["changes"])


def test_compare_foreign_strategy_returns_404(client):
    save_profile(client, expected_revision=0)
    response = client.post(
        "/api/strategy/00000000-0000-0000-0000-000000000099/compare",
        json={"plan_start_date": "2026-07-20"},
    )
    assert response.status_code == 404


def test_compare_does_not_create_strategy_record(client, tmp_path):
    save_profile(client, expected_revision=0)
    strategy_id = _save_strategy()

    async def _count():
        async with __import__("aiosqlite").connect(database.resolve_database_path()) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM weekly_strategies")
            row = await cursor.fetchone()
            await cursor.close()
            return row[0]

    before = asyncio.run(_count())
    client.post(
        f"/api/strategy/{strategy_id}/compare",
        json={"plan_start_date": "2026-07-20"},
    )
    assert asyncio.run(_count()) == before


def test_compare_token_works_for_generation(client, monkeypatch):
    save_profile(client, expected_revision=0)
    strategy_id = _save_strategy()

    async def fake_generate_menu(**kwargs):
        # Sprint 7.2: the result becomes a durable snapshot and must be a
        # valid MenuPlan, exactly like real generate_menu output.
        menu = build_valid_menu_dict(days=3)
        menu["plan_start_date"] = str(kwargs.get("plan_start_date", "2026-07-20"))
        return menu

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    compare = client.post(
        f"/api/strategy/{strategy_id}/compare",
        json={"plan_start_date": "2026-07-20"},
    )
    token = compare.json()["preview"]["preview_token"]
    generate = client.post("/api/generate-menu", json={"preview_token": token})
    assert generate.status_code == 200
    assert generate.json().get("strategy_id")
