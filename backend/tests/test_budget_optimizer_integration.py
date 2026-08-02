"""Integration-style Budget Optimizer convergence with mocked Claude pipeline."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest

import claude_service
import config
from strategy.models import WeeklyStrategy


def _result(shopping: float, budget: float = 5000) -> dict:
    usage = round(100.0 * shopping / budget, 1)
    return {
        "summary": "ok",
        "total_cost": shopping,
        "shopping_cost": shopping,
        "budget_limit": budget,
        "budget_usage_percent": usage,
        "recipe_cost": shopping,
        "days_plan": [],
        "recipes": [],
        "basket": [],
    }


def _strategy(budget: float = 5000) -> WeeklyStrategy:
    return WeeklyStrategy.model_validate(
        {
            "strategy_version": 5,
            "budget": budget,
            "days": 5,
            "meal_types": ["breakfast", "lunch", "dinner"],
            "meals_per_day": 3,
            "goal": "home",
            "preferred_proteins": ["chicken"],
            "cook_days": [1, 2, 3, 4, 5],
            "shopping_days": [1],
            "cooking_time_limit": 45,
            "leftovers_enabled": True,
            "repeat_breakfasts": False,
            "repeat_lunches": False,
            "repeat_dinners": False,
            "excluded_products": [],
            "generated_at": "2026-01-01T00:00:00Z",
        }
    )


@pytest.fixture
def enable_optimizer(monkeypatch):
    monkeypatch.setattr(config, "BUDGET_OPTIMIZER_ENABLED", True)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")


def _install_fake_llm(monkeypatch, process_results: list):
    """Fake Anthropic OK responses + sequential process_claude_response outcomes."""

    class FakeResponse:
        status_code = 200
        headers = {}
        content = b"{}"
        text = "{}"

        def json(self):
            return {
                "content": [{"type": "text", "text": "{}"}],
                "stop_reason": "end_turn",
                "usage": {"output_tokens": 10},
            }

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr(claude_service, "create_anthropic_client", lambda: FakeClient())
    monkeypatch.setattr(claude_service, "build_system_prompt", lambda *_a, **_k: "sys")
    monkeypatch.setattr(claude_service, "build_prompt", lambda *_a, **_k: "prompt")

    queue = list(process_results)

    def fake_process(*_args, **_kwargs):
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(claude_service, "process_claude_response", fake_process)
    return queue


def test_initial_in_target_makes_zero_optimizer_calls(monkeypatch, enable_optimizer):
    queue = _install_fake_llm(monkeypatch, [_result(4700)])
    calls = {"n": 0}
    original = claude_service.build_budget_optimizer_prompt

    def counting_prompt(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(claude_service, "build_budget_optimizer_prompt", counting_prompt)

    out = asyncio.run(
        claude_service.generate_menu(
            budget=5000,
            days=5,
            meal_types=["breakfast", "lunch", "dinner"],
            meals_per_day=3,
            persons=1,
            proteins=["chicken"],
            goal="home",
            cooktime="fast",
            allergies="",
            strategy=_strategy(),
            plan_start_date=date(2026, 1, 1),
        )
    )
    assert out["shopping_cost"] == 4700
    assert calls["n"] == 0
    assert queue == []


def test_candidate_in_target_accepted(monkeypatch, enable_optimizer):
    _install_fake_llm(monkeypatch, [_result(2803.67), _result(4700)])
    out = asyncio.run(
        claude_service.generate_menu(
            budget=5000,
            days=5,
            meal_types=["breakfast", "lunch", "dinner"],
            meals_per_day=3,
            persons=1,
            proteins=["chicken"],
            goal="home",
            cooktime="fast",
            allergies="",
            strategy=_strategy(),
            plan_start_date=date(2026, 1, 1),
        )
    )
    assert out["shopping_cost"] == 4700


def test_all_optimizer_failures_return_baseline(monkeypatch, enable_optimizer):
    from claude_exceptions import MenuConstraintError

    err = MenuConstraintError(
        "fail",
        issue_codes=["BUDGET_EXCEEDED", "LEFTOVER_SOURCE_INGREDIENT_MISSING"],
    )
    _install_fake_llm(monkeypatch, [_result(2803.67), err, err])
    out = asyncio.run(
        claude_service.generate_menu(
            budget=5000,
            days=5,
            meal_types=["breakfast", "lunch", "dinner"],
            meals_per_day=3,
            persons=1,
            proteins=["chicken"],
            goal="home",
            cooktime="fast",
            allergies="",
            strategy=_strategy(),
            plan_start_date=date(2026, 1, 1),
        )
    )
    assert out["shopping_cost"] == 2803.67


def test_second_optimizer_candidate_accepted_after_first_failure(
    monkeypatch, enable_optimizer
):
    from claude_exceptions import MenuConstraintError

    err = MenuConstraintError(
        "fail",
        issue_codes=["BUDGET_EXCEEDED", "LEFTOVER_SOURCE_INGREDIENT_MISSING"],
    )
    _install_fake_llm(monkeypatch, [_result(2803.67), err, _result(4700)])
    out = asyncio.run(
        claude_service.generate_menu(
            budget=5000,
            days=5,
            meal_types=["breakfast", "lunch", "dinner"],
            meals_per_day=3,
            persons=1,
            proteins=["chicken"],
            goal="home",
            cooktime="fast",
            allergies="",
            strategy=_strategy(),
            plan_start_date=date(2026, 1, 1),
        )
    )
    assert out["shopping_cost"] == 4700


def test_never_returns_over_budget_candidate(monkeypatch, enable_optimizer):
    # Valid process_claude_response would not return over-budget, but if it did,
    # optimizer must reject and fall back.
    _install_fake_llm(monkeypatch, [_result(2803.67), _result(5930), _result(5930)])
    out = asyncio.run(
        claude_service.generate_menu(
            budget=5000,
            days=5,
            meal_types=["breakfast", "lunch", "dinner"],
            meals_per_day=3,
            persons=1,
            proteins=["chicken"],
            goal="home",
            cooktime="fast",
            allergies="",
            strategy=_strategy(),
            plan_start_date=date(2026, 1, 1),
        )
    )
    assert out["shopping_cost"] == 2803.67
    assert out["shopping_cost"] <= 5000
