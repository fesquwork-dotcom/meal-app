"""Sprint 10.5.4 — budget utilization dual-cost and optimizer helpers."""

from __future__ import annotations

from menu_models import (
    BasketCategory,
    BasketItem,
    DayMeal,
    DayPlan,
    MenuPlan,
    Recipe,
    RecipeIngredient,
)
from shopping.budget_utilization import (
    build_budget_optimizer_prompt,
    build_budget_utilization_explanation,
    compute_budget_utilization,
    compute_recipe_cost,
)


def _menu(*, total_cost: float = 430.0) -> MenuPlan:
    return MenuPlan(
        summary="Тест",
        total_cost=total_cost,
        days_plan=[
            DayPlan(
                day="День 1",
                meals=[
                    DayMeal(
                        type="dinner",
                        recipe_name="Ужин",
                        meal_id="day1_dinner",
                        requires_cooking=True,
                        prepared_on_day=1,
                    )
                ],
            )
        ],
        recipes=[
            Recipe(
                name="Ужин",
                ingredients=[
                    RecipeIngredient(name="Куриная грудка", amount="500 г"),
                    RecipeIngredient(name="Картофель", amount="300 г"),
                ],
                steps=["Готовить"],
            )
        ],
        basket=[
            BasketCategory(
                category="Мясо",
                items=[BasketItem(name="Куриная грудка", weight="500 г", price=350)],
            ),
            BasketCategory(
                category="Овощи",
                items=[BasketItem(name="Картофель", weight="300 г", price=80)],
            ),
        ],
    )


def test_compute_recipe_cost_is_non_negative():
    cost = compute_recipe_cost(_menu())
    assert cost >= 0


def test_utilization_percent_and_target_flags():
    menu = _menu(total_cost=5870)
    util = compute_budget_utilization(menu, 6000)
    assert util is not None
    assert util.shopping_cost == 5870
    assert util.budget_limit == 6000
    assert 97.0 <= util.budget_usage_percent <= 98.0
    assert util.in_target_range is True
    assert util.underutilized is False
    fields = util.as_wire_fields()
    assert fields["shopping_cost"] == 5870
    assert "budget_usage_percent" in fields


def test_underutilized_when_below_90_percent():
    menu = _menu(total_cost=4000)
    util = compute_budget_utilization(menu, 6000)
    assert util is not None
    assert util.underutilized is True
    assert util.in_target_range is False


def test_explanation_mentions_usage_and_packages_when_gap():
    menu = _menu(total_cost=500)
    util = compute_budget_utilization(menu, 600)
    assert util is not None
    # Force a pack gap for the explanation path.
    from shopping.budget_utilization import BudgetUtilization

    forced = BudgetUtilization(
        budget_limit=600,
        recipe_cost=400,
        shopping_cost=500,
        budget_usage_percent=83.3,
        pack_gap=100,
        in_target_range=False,
        underutilized=True,
    )
    text = build_budget_utilization_explanation(forced)
    assert "Использовано" in text
    assert "упаковками" in text


def test_optimizer_prompt_forbids_extra_meals():
    prompt = build_budget_optimizer_prompt(
        budget_limit=6000,
        shopping_cost=4000,
        usage_percent=66.7,
    )
    assert "BUDGET OPTIMIZER" in prompt
    assert "добавлять блюда" in prompt or "добавляй блюда" in prompt
    assert "90–100%" in prompt or "90-100%" in prompt.replace("–", "-")


def test_invalid_budget_returns_none():
    assert compute_budget_utilization(_menu(), 0) is None
    assert compute_budget_utilization(_menu(), -10) is None
