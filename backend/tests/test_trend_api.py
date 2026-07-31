"""HTTP contract for GET /api/trends/summary."""

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


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "trends-api.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _seed_finalized_week(
    *, user_id: int, plan_start: date, replacements: int
) -> str:
    evaluation = DecisionEngine().evaluate({"days": 7, "goal": "home"})
    repository = StrategyRepository()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=user_id,
            strategy=evaluation.strategy,
            plan_start_date=plan_start,
            reason_codes=evaluation.reason_codes,
            decision_context=evaluation.decision,
            decision_trace=evaluation.trace,
        )
    )
    memory = MemoryRepository()
    for index in range(replacements):
        event = replace(
            _event(index),
            id=f"{strategy_id}-event-{index}",
            event_key=f"{strategy_id}-request-{index}",
            user_id=user_id,
            strategy_id=strategy_id,
        )
        asyncio.run(memory.insert_event(event))
    asyncio.run(repository.mark_completed(strategy_id, user_id))
    return strategy_id


def test_empty_history_returns_insufficient_summary(client):
    response = client.get("/api/trends/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == 1
    assert payload["confidence"]["status"] == "insufficient_data"
    assert payload["confidence"]["weeks"] == 0
    assert len(payload["metrics"]) == 5
    for metric in payload["metrics"]:
        assert metric["status"] == "insufficient_data"
        assert metric["value"] is None
        assert metric["change"] is None


def test_summary_reflects_finalized_weeks(client):
    for offset, replacements in enumerate((12, 12, 1, 1)):
        _seed_finalized_week(
            user_id=42,
            plan_start=date(2026, 5, 4 + offset * 7),
            replacements=replacements,
        )
    response = client.get("/api/trends/summary")
    assert response.status_code == 200
    payload = response.json()
    assert payload["confidence"]["weeks"] == 4
    assert payload["confidence"]["status"] == "emerging"
    replacement = next(
        metric for metric in payload["metrics"] if metric["id"] == "replacement_rate"
    )
    assert replacement["status"] == "improving"
    assert replacement["evidence_weeks"] == 4
    # Emerging: qualitative text only, no numbers.
    assert replacement["value"] is None
    assert replacement["change"] is None
    assert replacement["summary_text"] == "Есть первые признаки улучшения."


def test_active_strategy_does_not_count_as_evidence(client):
    evaluation = DecisionEngine().evaluate({"days": 7})
    asyncio.run(
        StrategyRepository().save_active(
            user_id=42,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 7, 13),
            reason_codes=evaluation.reason_codes,
            decision_context=evaluation.decision,
            decision_trace=evaluation.trace,
        )
    )
    response = client.get("/api/trends/summary")
    assert response.status_code == 200
    assert response.json()["confidence"]["weeks"] == 0


def test_summary_is_stable_across_repeated_requests(client):
    for offset in range(3):
        _seed_finalized_week(
            user_id=42, plan_start=date(2026, 6, 1 + offset * 7), replacements=2
        )
    first = client.get("/api/trends/summary").json()
    second = client.get("/api/trends/summary").json()
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second


def test_requires_authentication(client, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    response = client.get("/api/trends/summary")
    assert response.status_code == 401
