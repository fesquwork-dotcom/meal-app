"""Strategy API exposes only safe aggregate outcome summaries."""

import asyncio
from datetime import date

import aiosqlite
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
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "outcome-api.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _save_completed(*, with_trace: bool = True) -> str:
    evaluation = DecisionEngine().evaluate({"days": 7, "goal": "home"})
    repository = StrategyRepository()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=42,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 7, 1),
            reason_codes=evaluation.reason_codes,
            decision_context=evaluation.decision,
            decision_trace=evaluation.trace if with_trace else None,
        )
    )
    asyncio.run(repository.mark_completed(strategy_id, 42))
    return strategy_id


def test_by_id_evaluates_and_returns_safe_outcomes(client):
    strategy_id = _save_completed()
    # MemoryEventRecord is a frozen dataclass, not a Pydantic model.
    from dataclasses import replace

    event = replace(_event(0), strategy_id=strategy_id, user_id=42)
    asyncio.run(MemoryRepository().insert_event(event))

    response = client.get(f"/api/strategy/{strategy_id}")
    body = response.json()
    assert response.status_code == 200
    assert body["decision_outcomes"]["successful_count"] > 0
    assert len(body["decision_outcomes"]["explanations"]) <= 5
    for forbidden in (
        "private-event",
        "meal-private",
        "recipe-private",
        "private-ingredient",
        "evidence_count",
        "result",
        "feedback",
    ):
        assert forbidden not in response.text


def test_active_strategy_has_no_retrospective_outcomes(client):
    evaluation = DecisionEngine().evaluate({"days": 7})
    strategy_id = asyncio.run(
        StrategyRepository().save_active(
            user_id=42,
            strategy=evaluation.strategy,
            plan_start_date=date.today(),
            decision_trace=evaluation.trace,
        )
    )
    response = client.get(f"/api/strategy/{strategy_id}")
    assert response.status_code == 200
    assert response.json()["decision_outcomes"] is None


def test_legacy_strategy_without_trace_has_null_outcomes(client):
    strategy_id = _save_completed(with_trace=False)
    response = client.get(f"/api/strategy/{strategy_id}")
    assert response.status_code == 200
    assert response.json()["decision_outcomes"] is None


def test_malformed_outcomes_do_not_break_strategy_response(client):
    strategy_id = _save_completed()

    async def corrupt():
        async with aiosqlite.connect(database.resolve_database_path()) as db:
            await db.execute(
                "UPDATE weekly_strategies SET decision_outcomes_json = ? WHERE id = ?",
                ("{broken", strategy_id),
            )
            await db.commit()

    asyncio.run(corrupt())
    response = client.get(f"/api/strategy/{strategy_id}")
    assert response.status_code == 200
    assert response.json()["strategy"]["days"] == 7
    assert response.json()["decision_outcomes"] is None
