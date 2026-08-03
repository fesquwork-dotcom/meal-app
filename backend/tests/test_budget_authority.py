"""Sprint 10.8 — shopping_cost is the authoritative weekly budget metric."""

from __future__ import annotations

import json
import logging
from datetime import date

import pytest

import claude_service
import config
from claude_exceptions import MenuConstraintError
from menu_models import MenuPlan
from menu_validation import (
    MenuValidationRequest,
    validate_menu_plan,
    validate_shopping_budget,
)
from decimal import Decimal

from shopping.models import BasketBuildResult
from shopping.budget_utilization import build_budget_optimizer_prompt
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict
from tests.strategy_fixtures import build_test_strategy


def _request(**overrides) -> MenuValidationRequest:
    base = {
        "days": 3,
        "budget": 5000.0,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "meals_per_day": 3,
        "persons": 1,
        "cooktime": "medium",
        "allergies": "нет",
        "strategy_aware": True,
    }
    base.update(overrides)
    return MenuValidationRequest(**base)


def test_shopping_under_budget_passes_even_if_recipe_total_higher():
    """budget=5000, recipe/calculated-like 5400, shopping 4700 → pass."""
    issues = validate_shopping_budget(4700.0, 5000.0)
    assert issues == []


def test_shopping_over_budget_fails_even_if_recipe_total_lower():
    issues = validate_shopping_budget(5200.0, 5000.0)
    assert len(issues) == 1
    assert issues[0].code == "BUDGET_EXCEEDED"
    assert issues[0].meta is not None
    assert issues[0].meta["shopping_cost"] == 5200.0
    assert issues[0].meta["overshoot_amount"] == 200.0


def test_model_total_irrelevant_to_shopping_gate():
    # model_total=6000 but shopping=4800 → pass
    assert validate_shopping_budget(4800.0, 5000.0) == []
    # model_total=3000 but shopping=5100 → fail
    assert any(
        i.code == "BUDGET_EXCEEDED" for i in validate_shopping_budget(5100.0, 5000.0)
    )


def test_pre_basket_validation_skips_user_budget_when_disabled():
    menu = annotate_cooking_metadata(
        build_valid_menu_dict(days=3, cooktime="30 мин"),
        build_test_strategy(days=3, cooktime="medium", budget=3000),
    )
    # Inflate Claude basket / total far above budget — structural validators still OK.
    menu["total_cost"] = 5400.0
    for cat in menu["basket"]:
        for item in cat["items"]:
            item["price"] = 900.0
    plan = MenuPlan.model_validate(menu)
    result = validate_menu_plan(plan, _request(budget=3000), enforce_user_budget=False)
    assert not any(i.code == "BUDGET_EXCEEDED" for i in result.errors)


def test_post_basket_plan_enforces_shopping_on_total_cost():
    menu = annotate_cooking_metadata(
        build_valid_menu_dict(days=3, cooktime="30 мин"),
        build_test_strategy(days=3, cooktime="medium", budget=3000),
    )
    menu["total_cost"] = 5200.0
    for cat in menu["basket"]:
        n = max(1, len(cat["items"]))
        for item in cat["items"]:
            item["price"] = round(5200.0 / n, 2)
    # Fix sum drift
    items = menu["basket"][0]["items"]
    items[0]["price"] = round(
        5200.0 - sum(i["price"] for i in items[1:]),
        2,
    )
    plan = MenuPlan.model_validate(menu)
    result = validate_menu_plan(plan, _request(budget=5000), enforce_user_budget=True)
    assert any(i.code == "BUDGET_EXCEEDED" for i in result.errors)


def test_replace_meal_budget_uses_shopping_total_after_basket():
    """Post-merge plans already carry BasketEngine total_cost (= shopping_cost)."""
    from strategy.replacement_exceptions import ReplacementValidationError
    from strategy.replacement_service import MealReplacementService

    strategy = build_test_strategy(days=1, cooktime="fast", budget=3000)
    menu = annotate_cooking_metadata(
        build_valid_menu_dict(days=1, cooktime="15 мин"),
        strategy,
    )
    menu["total_cost"] = 3500.0
    items = menu["basket"][0]["items"]
    share = round(3500.0 / len(items), 2)
    for item in items:
        item["price"] = share
    items[0]["price"] = round(3500.0 - share * (len(items) - 1), 2)
    plan = MenuPlan.model_validate(menu)
    request = MenuValidationRequest(
        days=1,
        budget=3000,
        meal_types=list(strategy.meal_types),
        meals_per_day=strategy.meals_per_day,
        persons=1,
        cooktime="fast",
        allergies="нет",
        strategy_aware=True,
    )
    with pytest.raises(ReplacementValidationError) as exc_info:
        MealReplacementService._validate_merged_plan(
            MealReplacementService.__new__(MealReplacementService),
            plan,
            strategy,
            request,
        )
    assert "BUDGET_EXCEEDED" in exc_info.value.issue_codes


def test_process_allows_high_claude_basket_when_shopping_ok(monkeypatch, caplog):
    """Optimizer-style candidate: Claude basket sum > budget, BasketEngine shopping OK."""
    strategy = build_test_strategy(days=1, cooktime="fast", budget=5000)
    raw_menu = annotate_cooking_metadata(
        build_valid_menu_dict(days=1, cooktime="15 мин"),
        strategy,
    )
    raw_menu["total_cost"] = 5400.0
    for cat in raw_menu["basket"]:
        for item in cat["items"]:
            item["price"] = 1800.0

    def fake_build(menu, existing_basket=None, **_kwargs):
        # Authoritative shopping under budget despite high Claude estimate.
        basket = existing_basket or menu.basket
        return BasketBuildResult(
            basket=basket,
            total_cost=Decimal("4700.00"),
            unresolved_prices=[],
        )

    monkeypatch.setattr(claude_service, "build_basket_from_menu", fake_build)
    monkeypatch.setattr(config, "ENVIRONMENT", "development")

    with caplog.at_level(logging.INFO):
        result = claude_service.process_claude_response(
            json.dumps(raw_menu, ensure_ascii=False),
            MenuValidationRequest(
                days=1,
                budget=5000,
                meal_types=list(strategy.meal_types),
                meals_per_day=strategy.meals_per_day,
                persons=1,
                cooktime="fast",
                allergies="нет",
            ),
            request_id="req-budget-auth",
            user_id=1,
            started_at=0.0,
            strategy=strategy,
            plan_start_date=date(2026, 8, 3),
        )

    assert result["shopping_cost"] == 4700.0
    assert result["total_cost"] == 4700.0
    assert float(result.get("model_total") or 0) == 5400.0


def test_process_rejects_when_shopping_exceeds_budget(monkeypatch):
    strategy = build_test_strategy(days=1, cooktime="fast", budget=5000)
    raw_menu = annotate_cooking_metadata(
        build_valid_menu_dict(days=1, cooktime="15 мин"),
        strategy,
    )
    raw_menu["total_cost"] = 4300.0

    def fake_build(menu, existing_basket=None, **_kwargs):
        return BasketBuildResult(
            basket=existing_basket or menu.basket,
            total_cost=Decimal("5200.00"),
            unresolved_prices=[],
        )

    monkeypatch.setattr(claude_service, "build_basket_from_menu", fake_build)

    with pytest.raises(MenuConstraintError) as exc_info:
        claude_service.process_claude_response(
            json.dumps(raw_menu, ensure_ascii=False),
            MenuValidationRequest(
                days=1,
                budget=5000,
                meal_types=list(strategy.meal_types),
                meals_per_day=strategy.meals_per_day,
                persons=1,
                cooktime="fast",
                allergies="нет",
            ),
            request_id="req-over",
            user_id=1,
            started_at=0.0,
            strategy=strategy,
            plan_start_date=date(2026, 8, 3),
        )

    assert "BUDGET_EXCEEDED" in exc_info.value.issue_codes
    assert exc_info.value.menu_stats.get("shopping_cost") == 5200.0
    assert exc_info.value.menu_stats.get("budget_limit") == 5000.0
