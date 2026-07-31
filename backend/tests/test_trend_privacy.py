"""Trend API must expose aggregates only — never identifiers or raw evidence."""

import asyncio
from dataclasses import replace
from datetime import date

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from decision.engine import DecisionEngine
from memory.repository import MemoryRepository
from strategy.repository import StrategyRepository
from test_decision_outcomes import _event

FORBIDDEN_KEYS = {
    "strategy_id",
    "event_id",
    "memory_event_id",
    "meal_id",
    "recipe_id",
    "ingredient_id",
    "user_id",
    "revision",
    "decision_context",
    "profile",
    "event_key",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "trends-privacy.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _collect_keys(payload: object, keys: set[str]) -> None:
    if isinstance(payload, dict):
        for key, value in payload.items():
            keys.add(key)
            _collect_keys(value, keys)
    elif isinstance(payload, list):
        for item in payload:
            _collect_keys(item, keys)


def _seed(client) -> str:
    evaluation = DecisionEngine().evaluate({"days": 7})
    repository = StrategyRepository()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 6, 1),
            reason_codes=evaluation.reason_codes,
            decision_context=evaluation.decision,
            decision_trace=evaluation.trace,
        )
    )
    memory = MemoryRepository()
    for index in range(3):
        asyncio.run(
            memory.insert_event(
                replace(_event(index), user_id=42, strategy_id=strategy_id)
            )
        )
    asyncio.run(repository.mark_completed(strategy_id, 42))
    return strategy_id


def test_no_internal_keys_in_response(client):
    _seed(client)
    payload = client.get("/api/trends/summary").json()
    keys: set[str] = set()
    _collect_keys(payload, keys)
    assert keys & FORBIDDEN_KEYS == set()


def test_no_identifier_values_leak_into_texts(client):
    strategy_id = _seed(client)
    body = client.get("/api/trends/summary").text
    assert strategy_id not in body
    assert "private-event" not in body
    assert "meal-private" not in body
    assert "recipe-private" not in body
    assert "Private ingredient" not in body


def test_metric_sources_are_labels_not_tables(client):
    _seed(client)
    payload = client.get("/api/trends/summary").json()
    for metric in payload["metrics"]:
        assert "memory_events" not in metric["source"]
        assert "weekly_strategies" not in metric["source"]
        assert "learning_recommendations" not in metric["source"]
        assert "_json" not in metric["source"]
