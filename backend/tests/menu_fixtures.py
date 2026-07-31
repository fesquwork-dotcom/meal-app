"""Reusable menu plan fixtures for validation tests."""

from __future__ import annotations

from copy import deepcopy

from meal_types import DEFAULT_MEAL_TYPES


def build_valid_menu_dict(
    *,
    days: int = 3,
    budget: float = 3000.0,
    cooktime: str = "30 мин",
    meal_types: list[str] | None = None,
) -> dict[str, object]:
    selected_meal_types = meal_types or list(DEFAULT_MEAL_TYPES)
    days_plan: list[dict[str, str]] = []
    recipes: list[dict[str, object]] = []
    basket_items: list[dict[str, object]] = []

    meal_names = {
        "breakfast": ["Овсянка", "Сырники", "Омлет", "Творог", "Гречневая каша"],
        "lunch": ["Борщ", "Гречка с курицей", "Суп с фрикадельками", "Плов", "Лагман"],
        "dinner": [
            "Куриная грудка с рисом",
            "Рыба с овощами",
            "Тушёная капуста",
            "Котлеты с пюре",
            "Запечённая рыба",
        ],
        "snack": ["Йогурт", "Фрукты", "Орехи", "Смузи", "Творожок"],
    }

    total_price = 0.0
    meals_per_day = len(selected_meal_types)

    for day_index in range(days):
        legacy_day: dict[str, str] = {"day": f"День {day_index + 1}"}
        meals: list[dict[str, str]] = []
        for meal_type in selected_meal_types:
            names = meal_names.get(meal_type, ["Блюдо"])
            meal_name = names[day_index % len(names)]
            legacy_day[meal_type] = meal_name
            meals.append({"type": meal_type, "recipe_name": meal_name})

            if any(recipe["name"] == meal_name for recipe in recipes):
                continue

            recipes.append(
                {
                    "name": meal_name,
                    "emoji": "🍲",
                    "cook_time": cooktime,
                    "kbju": "Б:20г Ж:10г У:30г",
                    "ingredients": [
                        {"name": "Основной продукт", "amount": "300 г"},
                        {"name": "Соль", "amount": "по вкусу"},
                    ],
                    "steps": ["Подготовить ингредиенты", "Приготовить блюдо"],
                }
            )
            price = round(budget / (days * meals_per_day), 2)
            total_price += price
            basket_items.append(
                {
                    "name": "Основной продукт",
                    "weight": "300 г",
                    "price": price,
                }
            )

        days_plan.append({**legacy_day, "meals": meals})

    return {
        "summary": "Сбалансированное меню на несколько дней.",
        "total_cost": round(total_price, 2),
        "days_plan": days_plan,
        "recipes": recipes,
        "basket": [
            {
                "category": "Продукты",
                "items": basket_items,
            }
        ],
    }


def clone_menu(menu: dict[str, object]) -> dict[str, object]:
    return deepcopy(menu)


def annotate_cooking_metadata(
    menu_dict: dict[str, object],
    strategy,
) -> dict[str, object]:
    """Adds strategy-compliant cooking metadata to each meal in a menu dict."""
    menu = clone_menu(menu_dict)
    cook_days = set(strategy.cook_days)
    days_plan = menu.get("days_plan")
    if not isinstance(days_plan, list):
        return menu

    last_cook_source_id: str | None = None
    last_cook_prepared_day: int | None = None
    leftover_assigned = False

    for day_index, day in enumerate(days_plan):
        if not isinstance(day, dict):
            continue
        day_num = day_index + 1
        meals = day.get("meals")
        if not isinstance(meals, list):
            continue

        for meal in meals:
            if not isinstance(meal, dict):
                continue
            meal_type = meal.get("type", "meal")
            meal_id = f"day{day_num}_{meal_type}"
            recipe_id = f"recipe_{meal_id}"

            meal["meal_id"] = meal_id
            meal["recipe_id"] = recipe_id

            is_cook_day = day_num in cook_days
            can_reuse = (
                strategy.leftovers_enabled
                and last_cook_source_id is not None
                and day_num > 1
                and meal_type in {"lunch", "dinner"}
                and not leftover_assigned
            )

            if is_cook_day and meal_type in {"lunch", "dinner", "snack"} and not can_reuse:
                meal.update(
                    {
                        "meal_id": meal_id,
                        "requires_cooking": True,
                        "prepared_on_day": day_num,
                        "uses_leftovers": False,
                        "source_meal_id": None,
                    }
                )
                if meal_type in {"lunch", "dinner"}:
                    last_cook_source_id = meal_id
                    last_cook_prepared_day = day_num
            elif can_reuse and not leftover_assigned:
                meal.update(
                    {
                        "meal_id": meal_id,
                        "requires_cooking": False,
                        "prepared_on_day": last_cook_prepared_day,
                        "uses_leftovers": True,
                        "source_meal_id": last_cook_source_id,
                    }
                )
                leftover_assigned = True
            else:
                meal.update(
                    {
                        "meal_id": meal_id,
                        "requires_cooking": False,
                        "prepared_on_day": day_num,
                        "uses_leftovers": False,
                        "source_meal_id": None,
                    }
                )

    recipes = menu.get("recipes")
    if isinstance(recipes, list):
        recipe_ids_by_name: dict[str, str] = {}
        for day in days_plan:
            if not isinstance(day, dict):
                continue
            meals_list = day.get("meals")
            if not isinstance(meals_list, list):
                continue
            for meal in meals_list:
                if not isinstance(meal, dict):
                    continue
                name = meal.get("recipe_name")
                rid = meal.get("recipe_id")
                if isinstance(name, str) and isinstance(rid, str) and name and rid:
                    recipe_ids_by_name[name] = rid

        for recipe in recipes:
            if not isinstance(recipe, dict):
                continue
            name = recipe.get("name")
            if isinstance(name, str) and name in recipe_ids_by_name:
                recipe["recipe_id"] = recipe_ids_by_name[name]
            ingredients = recipe.get("ingredients")
            if not isinstance(ingredients, list):
                continue
            for ingredient in ingredients:
                if not isinstance(ingredient, dict):
                    continue
                if "contribution" not in ingredient:
                    ing_name = str(ingredient.get("name", "")).lower()
                    if ing_name in {"соль", "вода", "перец", "масло", "специи"}:
                        ingredient["contribution"] = "pantry"
                    else:
                        ingredient["contribution"] = "purchase"

        for day in days_plan:
            if not isinstance(day, dict):
                continue
            meals_list = day.get("meals")
            if not isinstance(meals_list, list):
                continue
            for meal in meals_list:
                if not isinstance(meal, dict) or not meal.get("uses_leftovers"):
                    continue
                recipe_name = meal.get("recipe_name")
                if not isinstance(recipe_name, str):
                    continue
                for recipe in recipes:
                    if not isinstance(recipe, dict) or recipe.get("name") != recipe_name:
                        continue
                    ingredients = recipe.get("ingredients")
                    if not isinstance(ingredients, list) or not ingredients:
                        continue
                    has_from_source = any(
                        ing.get("contribution") == "from_source"
                        for ing in ingredients
                        if isinstance(ing, dict)
                    )
                    if not has_from_source and ingredients:
                        first = ingredients[0]
                        if isinstance(first, dict):
                            first["contribution"] = "from_source"
                    for ingredient in ingredients[1:]:
                        if isinstance(ingredient, dict) and "contribution" not in ingredient:
                            ingredient["contribution"] = "purchase"

    meal_instances: dict[str, str] = {}
    for day in days_plan:
        if not isinstance(day, dict):
            continue
        meals_list = day.get("meals")
        if not isinstance(meals_list, list):
            continue
        for meal in meals_list:
            if not isinstance(meal, dict):
                continue
            meal_id = meal.get("meal_id")
            if not isinstance(meal_id, str):
                continue
            if meal.get("requires_cooking"):
                instance_id = f"cook_{meal_id}"
                meal["cooking_instance_id"] = instance_id
                meal_instances[meal_id] = instance_id

    for day in days_plan:
        if not isinstance(day, dict):
            continue
        meals_list = day.get("meals")
        if not isinstance(meals_list, list):
            continue
        for meal in meals_list:
            if not isinstance(meal, dict):
                continue
            if meal.get("cooking_instance_id"):
                continue
            source_id = meal.get("source_meal_id")
            if meal.get("uses_leftovers") and isinstance(source_id, str) and source_id in meal_instances:
                meal["cooking_instance_id"] = meal_instances[source_id]
            elif meal.get("meal_id"):
                meal["cooking_instance_id"] = f"cook_{meal['meal_id']}"

    return menu
