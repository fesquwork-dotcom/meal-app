"""Current/by-ID APIs expose explanations, never DecisionTrace."""

import asyncio
from datetime import date

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from decision.engine import DecisionEngine
from strategy.service import StrategyService


@pytest.fixture
def client(tmp_path, monkeypatch):
    path = tmp_path / "decision-explanation-api.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _save(*, with_trace: bool = True) -> str:
    result = DecisionEngine().evaluate(
        {"goal": "budget", "days": 7, "cooktime": "medium"}
    )
    return asyncio.run(
        StrategyService().save_active_strategy(
            user_id=42,
            strategy=result.strategy,
            plan_start_date=date.today(),
            reason_codes=result.reason_codes,
            decision_context=result.decision,
            decision_trace=result.trace if with_trace else None,
        )
    )


def test_current_strategy_returns_trace_explanations(client):
    _save()
    response = client.get("/api/strategy/current")
    body = response.json()
    assert response.status_code == 200
    assert body["decision_explanations"]["source"] == "trace"
    assert len(body["decision_explanations"]["explanations"]) <= 8
    assert "decision_trace" not in response.text
    assert "rule_code" not in response.text


def test_strategy_by_id_returns_explanations(client):
    strategy_id = _save()
    response = client.get(f"/api/strategy/{strategy_id}")
    assert response.status_code == 200
    assert response.json()["decision_explanations"]["source"] == "trace"


def test_status_none_has_null_decision_explanations(client):
    response = client.get("/api/strategy/current")
    assert response.status_code == 200
    assert response.json()["decision_explanations"] is None


def test_early_v5_without_trace_uses_legacy_fallback(client):
    strategy_id = _save(with_trace=False)
    response = client.get(f"/api/strategy/{strategy_id}")
    body = response.json()
    assert response.status_code == 200
    assert body["decision_explanations"]["source"] == "legacy"


def test_malformed_trace_uses_legacy_fallback(client):
    strategy_id = _save()

    async def corrupt():
        async with aiosqlite.connect(database.resolve_database_path()) as db:
            await db.execute(
                "UPDATE weekly_strategies SET decision_trace_json = ? WHERE id = ?",
                ("{broken", strategy_id),
            )
            await db.commit()

    asyncio.run(corrupt())
    response = client.get(f"/api/strategy/{strategy_id}")
    assert response.status_code == 200
    assert response.json()["decision_explanations"]["source"] == "legacy"


@pytest.mark.parametrize("strategy_version", [1, 2, 3, 4])
def test_legacy_strategy_versions_return_200_with_fallback(client, strategy_version):
    result = DecisionEngine().evaluate({"goal": "home", "days": 3})
    strategy = result.strategy.model_copy(
        update={"strategy_version": strategy_version}
    )
    strategy_id = asyncio.run(
        StrategyService().save_active_strategy(
            user_id=42,
            strategy=strategy,
            plan_start_date=date.today(),
            reason_codes=result.reason_codes,
        )
    )
    response = client.get(f"/api/strategy/{strategy_id}")
    assert response.status_code == 200
    assert response.json()["decision_explanations"]["source"] == "legacy"
