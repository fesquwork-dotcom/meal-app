"""Meal type helpers shared across API, validation, and prompts."""

from __future__ import annotations

from typing import Literal

MealType = Literal["breakfast", "lunch", "dinner", "snack"]

VALID_MEAL_TYPES: frozenset[str] = frozenset({"breakfast", "lunch", "dinner", "snack"})
DEFAULT_MEAL_TYPES: list[str] = ["breakfast", "lunch", "dinner"]

MEAL_TYPE_LABELS_RU: dict[str, str] = {
    "breakfast": "Завтрак",
    "lunch": "Обед",
    "dinner": "Ужин",
    "snack": "Перекус",
}


def meal_types_from_count(meals_per_day: int) -> list[str]:
    """Legacy compatibility mapping from meals_per_day."""
    if meals_per_day <= 1:
        return ["breakfast"]
    if meals_per_day == 2:
        return ["breakfast", "dinner"]
    if meals_per_day == 3:
        return ["breakfast", "lunch", "dinner"]
    return ["breakfast", "lunch", "dinner", "snack"]


def resolve_meal_types(
    meal_types: list[str] | None,
    meals_per_day: int | None = None,
) -> list[str]:
    """Resolves meal_types with legacy meals_per_day fallback."""
    if meal_types:
        resolved: list[str] = []
        for meal_type in meal_types:
            if meal_type in VALID_MEAL_TYPES and meal_type not in resolved:
                resolved.append(meal_type)
        if resolved:
            return resolved

    if meals_per_day is not None:
        return meal_types_from_count(meals_per_day)

    return list(DEFAULT_MEAL_TYPES)


def normalize_days_plan_payload(
    days_plan: list[object],
    selected_meal_types: list[str],
) -> list[dict[str, object]]:
    """Converts legacy breakfast/lunch/dinner day plans into meals[]."""
    normalized: list[dict[str, object]] = []

    for day in days_plan:
        if not isinstance(day, dict):
            continue

        day_copy: dict[str, object] = dict(day)
        existing_meals = day_copy.get("meals")

        if isinstance(existing_meals, list) and existing_meals:
            normalized.append(day_copy)
            continue

        legacy_map = {
            "breakfast": str(day_copy.get("breakfast", "")).strip(),
            "lunch": str(day_copy.get("lunch", "")).strip(),
            "dinner": str(day_copy.get("dinner", "")).strip(),
        }

        meals: list[dict[str, str]] = []
        for meal_type in selected_meal_types:
            if meal_type == "snack":
                continue
            recipe_name = legacy_map.get(meal_type, "")
            if recipe_name:
                meals.append({"type": meal_type, "recipe_name": recipe_name})

        day_copy["meals"] = meals
        normalized.append(day_copy)

    return normalized
