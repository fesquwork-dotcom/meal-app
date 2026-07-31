"""Privacy-safe presentation of decision-level trace changes."""

import asyncio
from datetime import date

from fastapi.testclient import TestClient

import config
import database
import main
from decision.engine import DecisionEngine
from decision.trace_models import DecisionRuleTrace
from decision.user_explanation import build_decision_explanation_changes
from strategy.repository import StrategyRepository
from tests.profile_test_helpers import save_profile


def test_value_change_is_presented():
    current = DecisionEngine().evaluate({"budget": 3000.0, "days": 5})
    nxt = DecisionEngine().evaluate({"budget": 4000.0, "days": 5})
    changes = build_decision_explanation_changes(
        current.trace,
        nxt.trace,
        current_strategy=current.strategy,
        next_strategy=nxt.strategy,
    )
    budget = next(change for change in changes if change.decision_key == "budget.weekly")
    assert budget.change_type == "value_changed"
    assert budget.before == "Около 3 000 ₽"
    assert budget.after == "Около 4 000 ₽"


def test_source_only_change_is_presented():
    current = DecisionEngine().evaluate({"days": 5})
    nxt = DecisionEngine().evaluate({"days": 5, "budget": 3000.0})
    changes = build_decision_explanation_changes(
        current.trace,
        nxt.trace,
        current_strategy=current.strategy,
        next_strategy=nxt.strategy,
    )
    budget = next(change for change in changes if change.decision_key == "budget.weekly")
    assert budget.change_type == "source_changed"
    assert budget.before == budget.after


def test_rule_only_change_is_presented():
    current = DecisionEngine().evaluate({"goal": "home", "days": 5})
    entry = next(
        item for item in current.trace.entries if item.decision_key == "shopping.days"
    )
    replacement = entry.model_copy(
        update={
            "applied_rules": [
                DecisionRuleTrace(
                    rule_code="SHOPPING_EQUIVALENT_RULE",
                    result="applied",
                    reason_code="SHOPPING_DAYS_SINGLE_TRIP",
                    input_summary={"days": 5},
                )
            ]
        }
    )
    next_trace = current.trace.model_copy(
        update={
            "entries": [
                replacement if item.decision_key == "shopping.days" else item
                for item in current.trace.entries
            ]
        }
    )
    changes = build_decision_explanation_changes(
        current.trace,
        next_trace,
        current_strategy=current.strategy,
        next_strategy=current.strategy,
    )
    shopping = next(change for change in changes if change.decision_key == "shopping.days")
    assert shopping.change_type == "rule_changed"


def test_no_change_returns_empty_list():
    result = DecisionEngine().evaluate({"goal": "home", "days": 5})
    changes = build_decision_explanation_changes(
        result.trace,
        result.trace,
        current_strategy=result.strategy,
        next_strategy=result.strategy,
    )
    assert changes == []


def test_missing_legacy_trace_returns_none():
    result = DecisionEngine().evaluate({"goal": "home", "days": 5})
    assert (
        build_decision_explanation_changes(
            None,
            result.trace,
            current_strategy=result.strategy,
            next_strategy=result.strategy,
        )
        is None
    )


def test_changes_are_stably_ordered_and_limited():
    current = DecisionEngine().evaluate({"goal": "budget", "days": 7, "budget": 3000})
    nxt = DecisionEngine().evaluate({"goal": "restaurant", "days": 5, "budget": 5000})
    first = build_decision_explanation_changes(
        current.trace,
        nxt.trace,
        current_strategy=current.strategy,
        next_strategy=nxt.strategy,
    )
    second = build_decision_explanation_changes(
        current.trace,
        nxt.trace,
        current_strategy=current.strategy,
        next_strategy=nxt.strategy,
    )
    assert first == second
    assert len(first) <= 8


def test_compare_api_returns_public_changes_without_trace(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "decision-compare.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    client = TestClient(main.app)
    save_profile(client, expected_revision=0, budget=5000)

    current = DecisionEngine().evaluate({"goal": "home", "days": 7, "budget": 3000})
    strategy_id = asyncio.run(
        StrategyRepository().save_active(
            user_id=42,
            strategy=current.strategy,
            plan_start_date=date(2026, 7, 20),
            reason_codes=current.reason_codes,
            decision_context=current.decision,
            decision_trace=current.trace,
        )
    )
    response = client.post(
        f"/api/strategy/{strategy_id}/compare",
        json={"plan_start_date": "2026-07-20"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["decision_changes"] is not None
    assert any(
        change["decision_key"] == "budget.weekly"
        for change in body["decision_changes"]
    )
    assert "decision_trace" not in response.text
    assert "rule_code" not in response.text
