from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from strategy.builder import StrategyBuilder
from strategy.service import StrategyService
from tests.menu_fixtures import build_valid_menu_dict
from tests.strategy_fixtures import build_test_profile, build_test_strategy


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "strategy-api.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)

    import asyncio

    asyncio.run(database.init_db())
    return TestClient(main.app)


def _save_active(user_id: int, days: int = 3, plan_start: date | None = None):
    import asyncio

    service = StrategyService()
    return asyncio.run(
        service.save_active_strategy(
            user_id=user_id,
            strategy=build_test_strategy(days=days),
            plan_start_date=plan_start or date.today(),
        )
    )


def test_current_strategy_returns_active(client):
    plan_start = date.today()
    strategy_id = _save_active(42, days=3, plan_start=plan_start)

    response = client.get("/api/strategy/current")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "active"
    assert body["strategy_id"] == strategy_id
    assert body["plan_start_date"] == plan_start.isoformat()
    assert body["plan_end_date"] == (plan_start + timedelta(days=2)).isoformat()
    assert body["strategy"]["days"] == 3


def test_current_strategy_none_when_missing(client):
    response = client.get("/api/strategy/current")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "none"
    assert body["strategy"] is None
    assert body["strategy_id"] is None


def test_expired_active_becomes_completed_and_returns_none(client, monkeypatch):
    past_start = date.today() - timedelta(days=10)
    _save_active(42, days=3, plan_start=past_start)

    response = client.get("/api/strategy/current")

    assert response.status_code == 200
    assert response.json()["status"] == "none"


def test_superseded_not_returned_as_current(client):
    service = StrategyService()
    import asyncio

    first_id = asyncio.run(
        service.save_active_strategy(
            user_id=42,
            strategy=build_test_strategy(days=3),
            plan_start_date=date.today(),
        )
    )
    second_id = asyncio.run(
        service.save_active_strategy(
            user_id=42,
            strategy=build_test_strategy(days=5),
            plan_start_date=date.today(),
        )
    )

    response = client.get("/api/strategy/current")
    body = response.json()

    assert body["strategy_id"] == second_id
    assert body["strategy_id"] != first_id


def test_get_strategy_by_id_requires_ownership(client):
    strategy_id = _save_active(42)

    response = client.get(f"/api/strategy/{strategy_id}")
    assert response.status_code == 200
    assert response.json()["strategy_id"] == strategy_id


def test_get_strategy_by_id_other_user_returns_404(client, monkeypatch):
    strategy_id = _save_active(42)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)

    response = client.get(f"/api/strategy/{strategy_id}")
    assert response.status_code == 404


def test_get_strategy_invalid_id_returns_404(client):
    response = client.get("/api/strategy/not-a-real-id")
    assert response.status_code == 404


def test_strategy_endpoints_require_auth(client, monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", False)
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "")

    assert client.get("/api/strategy/current").status_code == 401


def test_current_strategy_response_has_no_internal_fields(client):
    _save_active(42)

    body = client.get("/api/strategy/current").json()

    assert "strategy_json" not in body
    assert "user_id" not in body
    assert "created_at" not in body
    assert "reason_codes_json" not in body
    assert "decision_trace_json" not in body


def test_current_strategy_response_contains_explanation(client):
    _save_active(42, days=7, plan_start=date.today())

    body = client.get("/api/strategy/current").json()

    assert body["explanation"] is not None
    assert body["explanation"]["version"] == 1
    assert isinstance(body["explanation"]["headline"], str)
    assert isinstance(body["explanation"]["summary"], str)
    assert isinstance(body["explanation"]["reasons"], list)
    assert body["explanation"]["source"] in {"recorded", "inferred"}
    assert len(body["explanation"]["reasons"]) >= 1


def test_strategy_by_id_contains_explanation(client):
    strategy_id = _save_active(42, days=5)

    body = client.get(f"/api/strategy/{strategy_id}").json()

    assert body["explanation"] is not None
    assert body["explanation"]["headline"]
    assert body["strategy_id"] == strategy_id


def test_completed_strategy_by_id_returns_explanation(client, monkeypatch):
    past_start = date.today() - timedelta(days=10)
    strategy_id = _save_active(42, days=3, plan_start=past_start)

    client.get("/api/strategy/current")

    body = client.get(f"/api/strategy/{strategy_id}").json()
    assert body["status"] == "completed"
    assert body["explanation"] is not None


def test_none_current_response_keeps_explanation_null(client):
    body = client.get("/api/strategy/current").json()
    assert body["status"] == "none"
    assert body["explanation"] is None


def test_legacy_strategy_without_reason_codes_uses_inferred(client):
    strategy_id = _save_active(42)

    import asyncio
    import aiosqlite
    import config as app_config

    async def _clear_reason_codes():
        async with aiosqlite.connect(app_config.DATABASE_PATH) as db:
            await db.execute(
                "UPDATE weekly_strategies SET reason_codes_json = NULL WHERE id = ?",
                (strategy_id,),
            )
            await db.commit()

    asyncio.run(_clear_reason_codes())

    body = client.get(f"/api/strategy/{strategy_id}").json()
    assert body["explanation"]["source"] == "inferred"


def test_recorded_explanation_when_reason_codes_saved(client):
    build_result = StrategyBuilder().build_with_reasons(build_test_profile(days=7, goal="budget"))
    import asyncio

    service = StrategyService()
    strategy_id = asyncio.run(
        service.save_active_strategy(
            user_id=42,
            strategy=build_result.strategy,
            plan_start_date=date.today(),
            reason_codes=build_result.reason_codes,
        )
    )

    body = client.get(f"/api/strategy/{strategy_id}").json()
    assert body["explanation"]["source"] == "recorded"
    assert "GOAL_BUDGET" in {reason["code"] for reason in body["explanation"]["reasons"]}
