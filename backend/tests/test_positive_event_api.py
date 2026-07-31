"""Sprint 6.5 — POST /api/strategy/{id}/events contract and safety."""

import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from decision.engine import DecisionEngine
from strategy.repository import StrategyRepository
from strategy.service import StrategyService


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "positive-api.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _save_active(*, user_id: int = 42) -> str:
    evaluation = DecisionEngine().evaluate({"days": 7, "goal": "home"})
    return asyncio.run(
        StrategyRepository().save_active(
            user_id=user_id,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 7, 1),
            reason_codes=evaluation.reason_codes,
            decision_context=evaluation.decision,
            decision_trace=evaluation.trace,
        )
    )


def test_records_meal_event_and_deduplicates(client):
    strategy_id = _save_active()
    payload = {"event_type": "meal_cooked", "meal_id": "d1-private-breakfast"}

    first = client.post(f"/api/strategy/{strategy_id}/events", json=payload)
    assert first.status_code == 200
    assert first.json() == {"recorded": True, "deduplicated": False}
    # Response never echoes meal identifiers back.
    assert "d1-private-breakfast" not in first.text

    second = client.post(f"/api/strategy/{strategy_id}/events", json=payload)
    assert second.status_code == 200
    assert second.json() == {"recorded": False, "deduplicated": True}


def test_meal_event_can_be_undone_and_recorded_again(client):
    strategy_id = _save_active()
    payload = {"event_type": "meal_cooked", "meal_id": "d1-breakfast"}
    assert client.post(f"/api/strategy/{strategy_id}/events", json=payload).status_code == 200

    undone = client.request(
        "DELETE",
        f"/api/strategy/{strategy_id}/events",
        json=payload,
    )
    assert undone.status_code == 200
    assert undone.json() == {"removed": True, "absent": False}

    repeated = client.request(
        "DELETE",
        f"/api/strategy/{strategy_id}/events",
        json=payload,
    )
    assert repeated.status_code == 200
    assert repeated.json() == {"removed": False, "absent": True}

    recorded_again = client.post(f"/api/strategy/{strategy_id}/events", json=payload)
    assert recorded_again.json() == {"recorded": True, "deduplicated": False}


def test_plan_completed_can_be_undone(client):
    strategy_id = _save_active()
    payload = {"event_type": "plan_completed"}
    client.post(f"/api/strategy/{strategy_id}/events", json=payload)
    response = client.request(
        "DELETE",
        f"/api/strategy/{strategy_id}/events",
        json=payload,
    )
    assert response.status_code == 200
    assert response.json()["removed"] is True


def test_records_strategy_scoped_events(client):
    strategy_id = _save_active()
    for event_type in ("shopping_completed", "plan_completed"):
        response = client.post(
            f"/api/strategy/{strategy_id}/events",
            json={"event_type": event_type},
        )
        assert response.status_code == 200
        assert response.json()["recorded"] is True


def test_invalid_event_type_and_missing_meal_id_are_422(client):
    strategy_id = _save_active()

    bad_type = client.post(
        f"/api/strategy/{strategy_id}/events",
        json={"event_type": "meal_replaced"},
    )
    assert bad_type.status_code == 422
    assert bad_type.json()["code"] == "POSITIVE_EVENT_INVALID"

    no_meal = client.post(
        f"/api/strategy/{strategy_id}/events",
        json={"event_type": "meal_suited"},
    )
    assert no_meal.status_code == 422
    assert no_meal.json()["code"] == "POSITIVE_EVENT_INVALID"


def test_extra_fields_are_rejected(client):
    strategy_id = _save_active()
    response = client.post(
        f"/api/strategy/{strategy_id}/events",
        json={"event_type": "plan_completed", "note": "free text"},
    )
    assert response.status_code == 422


def test_unknown_strategy_is_404(client):
    response = client.post(
        "/api/strategy/does-not-exist/events",
        json={"event_type": "plan_completed"},
    )
    assert response.status_code == 404
    assert response.json()["code"] == "STRATEGY_NOT_FOUND"


def test_superseded_strategy_is_409(client):
    service = StrategyService()
    first = DecisionEngine().evaluate({"days": 7})
    first_id = asyncio.run(
        service.save_active_strategy(
            user_id=42,
            strategy=first.strategy,
            plan_start_date=date(2026, 7, 1),
            decision_trace=first.trace,
        )
    )
    second = DecisionEngine().evaluate({"days": 5})
    asyncio.run(
        service.save_active_strategy(
            user_id=42,
            strategy=second.strategy,
            plan_start_date=date(2026, 7, 8),
            decision_trace=second.trace,
        )
    )
    response = client.post(
        f"/api/strategy/{first_id}/events",
        json={"event_type": "plan_completed"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "POSITIVE_EVENT_NOT_ALLOWED"


def test_positive_events_become_outcome_evidence_after_completion(client):
    strategy_id = _save_active()
    for payload in (
        {"event_type": "meal_cooked", "meal_id": "d1-breakfast"},
        {"event_type": "meal_cooked", "meal_id": "d1-lunch"},
        {"event_type": "shopping_completed"},
        {"event_type": "plan_completed"},
    ):
        assert (
            client.post(f"/api/strategy/{strategy_id}/events", json=payload).status_code
            == 200
        )

    asyncio.run(StrategyRepository().mark_completed(strategy_id, 42))
    response = client.get(f"/api/strategy/{strategy_id}")
    assert response.status_code == 200
    outcomes = response.json()["decision_outcomes"]
    assert outcomes is not None
    assert outcomes["successful_count"] > 0
    assert outcomes["insufficient_data_count"] == 0
    # Aggregate summary must not leak event internals.
    for forbidden in ("d1-breakfast", "event_key", "meal_cooked", "shopping_completed"):
        assert forbidden not in response.text
