"""Prompt builder for single-meal replacement within an active strategy."""

from __future__ import annotations

import json

from menu_models import BasketCategory
from shopping.pricing import FALLBACK_PRICES
from strategy.models import WeeklyStrategy
from strategy.prompt import (
    CONTRIBUTION_CORRECTION_RULE,
    COOKING_CONTRACT_INSTRUCTIONS,
    strategy_to_prompt_dict,
)
from strategy.replacement_context import ReplacementContext
from recipe_identity import find_recipe_by_id

_REPLACEMENT_CONTRIBUTION_CONTRACT = (
    "Каждый ingredient в replacement recipe содержит contribution: "
    "purchase | from_source | pantry.\n"
    "pantry — ТОЛЬКО если название ингредиента буквально: соль, вода, перец, "
    "масло, специи; именованные специи и добавки (паприка, кумин, зелень, мёд "
    "и т.п.) — purchase."
)

_MAX_CORRECTION_PRODUCT_NAMES = 24
_MAX_NAME_CHARS = 40

PRICE_UNRESOLVED_CORRECTION_RULE = (
    "Некоторые ингредиенты невозможно сопоставить с доступным каталогом цен.\n"
    "Замени их доступными близкими продуктами, не меняя тип приёма пищи, "
    "ограничения, время приготовления и назначение блюда.\n"
    "Верни полный исправленный replacement JSON."
)


def _truncate_label(name: str) -> str:
    stripped = " ".join(name.split())
    if len(stripped) <= _MAX_NAME_CHARS:
        return stripped
    return stripped[: _MAX_NAME_CHARS - 1] + "…"


def collect_resolvable_product_labels(
    basket: list[BasketCategory] | None,
) -> list[str]:
    """Server-owned labels the price pipeline can resolve today.

    Replacement has no LLM basket: prices come from existing basket hints
    plus the small FALLBACK_PRICES table. Expose only that set to the model.
    """
    labels: set[str] = set()
    for category in basket or []:
        for item in category.items:
            label = _truncate_label(item.name)
            if label:
                labels.add(label)
    for key in FALLBACK_PRICES:
        label = _truncate_label(key)
        if label:
            labels.add(label)
    return sorted(labels)[:_MAX_CORRECTION_PRODUCT_NAMES]


def build_replacement_system_prompt(strategy: WeeklyStrategy) -> str:
    return (
        "Ты — помощник по замене одного блюда в существующем недельном плане питания.\n"
        "WEEKLY_STRATEGY — единственный источник истины. Не меняй стратегию, другие блюда, "
        "plan_start_date, strategy_id, meal_id, meal type или номер дня.\n"
        "Верни ТОЛЬКО один JSON-объект без markdown.\n"
        f"{_REPLACEMENT_CONTRIBUTION_CONTRACT}\n"
        f"{COOKING_CONTRACT_INSTRUCTIONS}"
    )


def _serialize_recipe(recipe) -> dict[str, object] | None:
    if recipe is None:
        return None
    return recipe.model_dump(mode="json")


def _serialize_meal(meal) -> dict[str, object]:
    return meal.model_dump(mode="json")


def build_replacement_user_prompt(
    context: ReplacementContext,
    reason: str | None,
) -> str:
    target = context.target
    day = context.menu_plan.days_plan[target.meal_ref.day_index]
    same_day_meals = [_serialize_meal(meal) for meal in day.meals]

    nearby_days: list[dict[str, object]] = []
    for offset in (-1, 0, 1):
        idx = target.meal_ref.day_index + offset
        if 0 <= idx < len(context.menu_plan.days_plan):
            day_plan = context.menu_plan.days_plan[idx]
            nearby_days.append(
                {
                    "day_number": idx + 1,
                    "day_label": day_plan.day,
                    "meals": [_serialize_meal(meal) for meal in day_plan.meals],
                }
            )

    downstream = [
        {
            "meal_id": ref.meal.meal_id,
            "day_number": ref.day_index + 1,
            "meal": _serialize_meal(ref.meal),
            "recipe": _serialize_recipe(
                find_recipe_by_id(context.menu_plan.recipes, ref.meal.recipe_id)
                if ref.meal.recipe_id
                else next(
                    (
                        recipe
                        for recipe in context.menu_plan.recipes
                        if recipe.name.strip().lower() == ref.meal.recipe_name.strip().lower()
                    ),
                    None,
                )
            ),
        }
        for ref in target.downstream_refs
    ]

    strategy_payload = json.dumps(
        strategy_to_prompt_dict(context.strategy),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    )

    reason_block = (
        f"Пожелание пользователя (низший приоритет, не нарушай стратегию): {reason}"
        if reason
        else "Пожелание пользователя не указано."
    )

    downstream_block = (
        json.dumps(downstream, ensure_ascii=False, indent=2)
        if downstream
        else "[]"
    )

    return f"""Замени ОДНО блюдо в существующем плане.

WEEKLY_STRATEGY (AUTHORITATIVE):
{strategy_payload}

TARGET MEAL (заменить только это блюдо):
- meal_id: {target.meal_ref.meal.meal_id} (НЕ МЕНЯТЬ)
- day_number: {target.day_number} (НЕ МЕНЯТЬ)
- meal_type: {target.meal_ref.meal.type} (НЕ МЕНЯТЬ)
- current_cooking_instance_id: {target.meal_ref.meal.cooking_instance_id}
- current_recipe_id: {target.meal_ref.meal.recipe_id}
- current_recipe_name: {target.meal_ref.meal.recipe_name}
- current_meal: {json.dumps(_serialize_meal(target.meal_ref.meal), ensure_ascii=False)}
- current_recipe: {json.dumps(_serialize_recipe(target.recipe), ensure_ascii=False)}

SAME DAY MEALS:
{json.dumps(same_day_meals, ensure_ascii=False, indent=2)}

NEARBY DAYS:
{json.dumps(nearby_days, ensure_ascii=False, indent=2)}

DOWNSTREAM MEALS (source_meal_id == target meal_id):
{downstream_block}

{reason_block}

Текущий total_cost плана: {context.menu_plan.total_cost}
Бюджет стратегии: {context.strategy.budget}

Верни JSON строго в формате:
{{
  "replacement": {{
    "meal": {{
      "type": "{target.meal_ref.meal.type}",
      "recipe_id": "{target.meal_ref.meal.recipe_id or f'recipe_{target.meal_ref.meal.meal_id}'}",
      "cooking_instance_id": "{target.meal_ref.meal.cooking_instance_id or f'cook_{target.meal_ref.meal.meal_id}'}",
      "recipe_name": "Новое блюдо",
      "meal_id": "{target.meal_ref.meal.meal_id}",
      "requires_cooking": true,
      "prepared_on_day": {target.day_number},
      "uses_leftovers": false,
      "source_meal_id": null
    }},
    "recipe": {{
      "recipe_id": "{target.meal_ref.meal.recipe_id or f'recipe_{target.meal_ref.meal.meal_id}'}",
      "name": "Новое блюдо",
      "emoji": "🍲",
      "cook_time": "30 мин",
      "kbju": "Б:20г Ж:10г У:30г",
      "ingredients": [{{"name": "продукт", "amount": "200 г", "contribution": "purchase"}}],
      "steps": ["Шаг 1", "Шаг 2"]
    }}
  }},
  "affected_meals": []
}}

Правила:
- recipe_id target meal СОХРАНИТЬ (логическая замена на месте).
- cooking_instance_id target meal СОХРАНИТЬ, если это та же cooking session.
- meal_id target meal НЕ МЕНЯТЬ.
- meal type и day НЕ МЕНЯТЬ.
- Не возвращай весь MenuPlan и не возвращай basket.
- Корзина будет пересобрана приложением из recipes.
- affected_meals — только прямые downstream meals, если их cooking metadata нужно обновить (максимум {len(target.downstream_refs)}).
- Если downstream meals есть, replacement должен остаться валидным source ИЛИ обнови affected_meals.
- Соблюдай exclusions, cook_days, cooking_time_limit, budget.
- Не меняй unrelated meals."""


def build_replacement_correction_prompt(
    issue_codes: list[str],
    messages: list[str],
    context: ReplacementContext,
    target_meal_id: str,
    *,
    unresolved_items: list[str] | tuple[str, ...] | None = None,
) -> str:
    violations = "\n".join(f"- {code}: {msg}" for code, msg in zip(issue_codes, messages))
    contribution_rule = (
        f"\n{CONTRIBUTION_CORRECTION_RULE}\n"
        if "INGREDIENT_CONTRIBUTION_INVALID" in issue_codes
        else ""
    )
    price_rule = ""
    if "REPLACEMENT_PRICE_UNRESOLVED" in issue_codes:
        unresolved = [
            _truncate_label(name)
            for name in (unresolved_items or ())
            if name and name.strip()
        ][:_MAX_CORRECTION_PRODUCT_NAMES]
        available = collect_resolvable_product_labels(context.menu_plan.basket)
        unresolved_block = (
            "\n".join(f"- {name}" for name in unresolved) if unresolved else "- (не указано)"
        )
        available_block = (
            ", ".join(available) if available else "(используй распространённые продукты из текущего плана)"
        )
        price_rule = (
            f"\n{PRICE_UNRESOLVED_CORRECTION_RULE}\n"
            f"Ингредиенты без цены:\n{unresolved_block}\n"
            f"Доступные продукты с известной ценой (ориентир, не полный каталог): "
            f"{available_block}\n"
        )
    return (
        "ИСПРАВЛЕНИЕ: предыдущая замена нарушила стратегию или контракт.\n"
        f"Нарушения:\n{violations}\n"
        f"{contribution_rule}"
        f"{price_rule}\n"
        f"Заменяемое meal_id: {target_meal_id}\n"
        f"День: {context.target.day_number}, тип: {context.target.meal_ref.meal.type}\n\n"
        "Исправь ТОЛЬКО replacement и при необходимости affected_meals. "
        "Не меняй meal_id, meal type, day, strategy, unrelated meals. "
        "Верни тот же JSON-контракт замены."
    )
