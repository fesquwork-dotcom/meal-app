"""Fake Anthropic client for offline stress runs and unit tests."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from strategy.models import WeeklyStrategy


@dataclass
class FakeClaudeController:
    """Controls fake HTTP responses for generate_menu during stress tests."""

    mode: str = "success_first"
    """success_first | success_after_retry | always_constraint | unexpected | truncate"""

    strategy: WeeklyStrategy | None = None
    call_count: int = 0
    prompts: list[str] = field(default_factory=list)
    menu_builder: Callable[[WeeklyStrategy], dict[str, object]] | None = None


def _fit_basket_to_budget(menu: dict[str, object], budget: float) -> None:
    """Make basket item prices sum to <= budget (avoid BUDGET_EXCEEDED from rounding)."""
    basket = menu.get("basket")
    if not isinstance(basket, list):
        return
    items: list[dict[str, object]] = []
    for category in basket:
        if isinstance(category, dict) and isinstance(category.get("items"), list):
            for item in category["items"]:
                if isinstance(item, dict):
                    items.append(item)
    if not items:
        menu["total_cost"] = 0.0
        return
    target = round(max(0.0, float(budget) - 0.01), 2)
    n = len(items)
    unit = round(target / n, 2) if n else 0.0
    running = 0.0
    for item in items[:-1]:
        item["price"] = unit
        running += unit
    items[-1]["price"] = round(max(0.0, target - running), 2)
    menu["total_cost"] = round(sum(float(item["price"]) for item in items), 2)


def _sync_meal_recipe_ids(menu: dict[str, object]) -> None:
    """Point each meal.recipe_id at an existing recipe entry for its name."""
    recipes = menu.get("recipes")
    days_plan = menu.get("days_plan")
    if not isinstance(recipes, list) or not isinstance(days_plan, list):
        return
    name_to_id: dict[str, str] = {}
    for recipe in recipes:
        if not isinstance(recipe, dict):
            continue
        name = recipe.get("name")
        rid = recipe.get("recipe_id")
        if isinstance(name, str) and isinstance(rid, str) and name and rid:
            name_to_id[name] = rid
    for day in days_plan:
        if not isinstance(day, dict):
            continue
        meals = day.get("meals")
        if not isinstance(meals, list):
            continue
        for meal in meals:
            if not isinstance(meal, dict):
                continue
            name = meal.get("recipe_name")
            if isinstance(name, str) and name in name_to_id:
                meal["recipe_id"] = name_to_id[name]


def _sanitize_contributions(menu: dict[str, object]) -> None:
    """Ensure from_source only appears on recipes used exclusively by leftover meals."""
    recipes = menu.get("recipes")
    days_plan = menu.get("days_plan")
    if not isinstance(recipes, list) or not isinstance(days_plan, list):
        return

    leftover_recipe_ids: set[str] = set()
    non_leftover_recipe_ids: set[str] = set()
    for day in days_plan:
        if not isinstance(day, dict):
            continue
        meals = day.get("meals")
        if not isinstance(meals, list):
            continue
        for meal in meals:
            if not isinstance(meal, dict):
                continue
            rid = meal.get("recipe_id")
            if not isinstance(rid, str) or not rid:
                continue
            if meal.get("uses_leftovers"):
                leftover_recipe_ids.add(rid)
            else:
                non_leftover_recipe_ids.add(rid)

    for recipe in recipes:
        if not isinstance(recipe, dict):
            continue
        rid = recipe.get("recipe_id")
        ingredients = recipe.get("ingredients")
        if not isinstance(ingredients, list):
            continue
        only_leftover = (
            isinstance(rid, str)
            and rid in leftover_recipe_ids
            and rid not in non_leftover_recipe_ids
        )
        for ingredient in ingredients:
            if not isinstance(ingredient, dict):
                continue
            name = str(ingredient.get("name") or "").strip().lower()
            if name in {"соль", "вода", "перец", "масло", "специи"}:
                ingredient["contribution"] = "pantry"
                continue
            if only_leftover and ingredient is ingredients[0]:
                ingredient["contribution"] = "from_source"
            else:
                ingredient["contribution"] = "purchase"


def _ensure_leftover_if_required(menu: dict[str, object], strategy: WeeklyStrategy) -> None:
    """annotate_cooking_metadata only reuses lunch/dinner; breakfast-only weeks need a link."""
    if not strategy.leftovers_enabled or strategy.days <= 1:
        return
    days_plan = menu.get("days_plan")
    if not isinstance(days_plan, list) or len(days_plan) < 2:
        return

    has_leftover = False
    source_meal: dict[str, object] | None = None
    for day in days_plan:
        if not isinstance(day, dict):
            continue
        meals = day.get("meals")
        if not isinstance(meals, list):
            continue
        for meal in meals:
            if not isinstance(meal, dict):
                continue
            if meal.get("uses_leftovers"):
                has_leftover = True
            if source_meal is None and isinstance(meal.get("meal_id"), str):
                source_meal = meal

    if has_leftover or source_meal is None:
        return

    source_meal["requires_cooking"] = True
    source_meal["uses_leftovers"] = False
    source_meal["source_meal_id"] = None
    if source_meal.get("prepared_on_day") is None:
        source_meal["prepared_on_day"] = 1
    if not source_meal.get("cooking_instance_id") and isinstance(source_meal.get("meal_id"), str):
        source_meal["cooking_instance_id"] = f"cook_{source_meal['meal_id']}"

    day2 = days_plan[1]
    if not isinstance(day2, dict):
        return
    meals2 = day2.get("meals")
    if not isinstance(meals2, list) or not meals2:
        return
    target = meals2[0]
    if not isinstance(target, dict):
        return
    target["uses_leftovers"] = True
    target["requires_cooking"] = False
    target["source_meal_id"] = source_meal.get("meal_id")
    target["prepared_on_day"] = source_meal.get("prepared_on_day") or 1
    target["cooking_instance_id"] = source_meal.get("cooking_instance_id")

    # Leftover meal needs from_source on its dedicated recipe.
    target_rid = target.get("recipe_id")
    recipes = menu.get("recipes")
    if not isinstance(recipes, list) or not isinstance(target_rid, str):
        return
    for recipe in recipes:
        if not isinstance(recipe, dict) or recipe.get("recipe_id") != target_rid:
            continue
        ingredients = recipe.get("ingredients")
        if not isinstance(ingredients, list) or not ingredients:
            continue
        first = ingredients[0]
        if isinstance(first, dict):
            first["contribution"] = "from_source"
        break


def _default_menu_builder(strategy: WeeklyStrategy) -> dict[str, object]:
    from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict

    cook_label = f"{max(10, min(int(strategy.cooking_time_limit), 90))} мин"
    menu = build_valid_menu_dict(
        days=strategy.days,
        budget=float(strategy.budget),
        cooktime=cook_label,
        meal_types=list(strategy.meal_types),
    )
    # Unique names per slot avoid shared recipe_id collisions after annotation
    # (from_source on a leftover recipe must not leak to independent meals).
    recipes_by_name: dict[str, dict[str, object]] = {}
    new_recipes: list[dict[str, object]] = []
    for day_index, day in enumerate(menu["days_plan"]):
        if not isinstance(day, dict):
            continue
        meals = day.get("meals")
        if not isinstance(meals, list):
            continue
        for meal in meals:
            if not isinstance(meal, dict):
                continue
            meal_type = str(meal.get("type") or "meal")
            # Neutral labels: profile allergies must not match recipe/ingredient text.
            unique_name = f"Блюдо QA д{day_index + 1} {meal_type}"
            meal["recipe_name"] = unique_name
            if unique_name not in recipes_by_name:
                recipe = {
                    "name": unique_name,
                    "emoji": "🍲",
                    "cook_time": cook_label,
                    "kbju": "Б:20г Ж:10г У:30г",
                    "ingredients": [
                        {"name": "Основной продукт", "amount": "300 г"},
                        {"name": "Соль", "amount": "по вкусу"},
                    ],
                    "steps": ["Подготовить ингредиенты", "Приготовить блюдо"],
                }
                recipes_by_name[unique_name] = recipe
                new_recipes.append(recipe)
    menu["recipes"] = new_recipes
    menu["basket"] = [
        {
            "category": "Продукты",
            "items": [
                {"name": "Основной продукт", "weight": "300 г", "price": 0.0}
                for _ in new_recipes
            ],
        }
    ]
    menu = annotate_cooking_metadata(menu, strategy)
    _ensure_leftover_if_required(menu, strategy)
    _sync_meal_recipe_ids(menu)
    _sanitize_contributions(menu)
    _fit_basket_to_budget(menu, float(strategy.budget))
    menu["total_cost"] = round(float(menu["total_cost"]) * 0.5 + 17.0, 2)
    return menu


def _constraint_failing_menu(strategy: WeeklyStrategy) -> dict[str, object]:
    """Valid schema, but excessive duplicates to force MenuConstraintError."""
    menu = _default_menu_builder(strategy)
    if strategy.days <= 1:
        for recipe in menu["recipes"]:
            if isinstance(recipe, dict):
                recipe["cook_time"] = "999 мин"
        return menu
    source = menu["days_plan"][0]["meals"][0]
    assert isinstance(source, dict)
    for day in menu["days_plan"]:
        if not isinstance(day, dict):
            continue
        meals = day.get("meals")
        if not isinstance(meals, list) or not meals:
            continue
        meal = meals[0]
        if not isinstance(meal, dict):
            continue
        meal["recipe_name"] = source["recipe_name"]
        if source.get("recipe_id"):
            meal["recipe_id"] = source["recipe_id"]
        meal["uses_leftovers"] = False
        meal["source_meal_id"] = None
    _sync_meal_recipe_ids(menu)
    # Keep prices valid; duplicate issue alone is enough for controlled failure.
    _fit_basket_to_budget(menu, float(strategy.budget))
    menu["total_cost"] = round(float(menu["total_cost"]) * 0.5 + 17.0, 2)
    return menu


def make_http_response(status_code: int, json_body: dict[str, object]) -> Any:
    from tests.test_anthropic_retry import make_http_response as _make

    return _make(status_code, json_body=json_body)


def build_fake_client(controller: FakeClaudeController):
    """Return an async context-manager client factory bound to controller."""

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **kwargs):
            controller.call_count += 1
            body = kwargs.get("json") or {}
            messages = body.get("messages") or []
            if messages and isinstance(messages[0], dict):
                controller.prompts.append(str(messages[0].get("content") or ""))

            strategy = controller.strategy
            if strategy is None:
                raise RuntimeError("FakeClaudeController.strategy must be set before generate_menu")

            builder = controller.menu_builder or _default_menu_builder
            mode = controller.mode

            if mode == "unexpected":
                raise RuntimeError("injected unexpected fake client failure")

            if mode == "truncate":
                return make_http_response(
                    200,
                    {
                        "stop_reason": "max_tokens",
                        "usage": {"output_tokens": 16000},
                        "content": [],
                    },
                )

            if mode == "always_constraint":
                payload = _constraint_failing_menu(strategy)
            elif mode == "success_after_retry":
                if controller.call_count == 1:
                    payload = _constraint_failing_menu(strategy)
                else:
                    payload = builder(strategy)
            else:
                payload = builder(strategy)

            text = json.dumps(payload, ensure_ascii=False)
            return make_http_response(
                200,
                {
                    "stop_reason": "end_turn",
                    "usage": {"output_tokens": max(500, len(text) // 4)},
                    "content": [{"type": "text", "text": text}],
                },
            )

    return lambda: FakeClient()
