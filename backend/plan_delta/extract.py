"""Pure extraction of comparable characteristics from a stored plan dict.

Input is the parsed ``plan_json`` of a durable revision. Extraction is
lenient about structure (malformed pieces yield ``None``) but strict about
honesty: a characteristic is returned only when it is fully computable.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class PlanCharacteristics:
    """Aggregates for one plan variant. ``None`` means "cannot be computed"."""

    total_cost: float | None
    basket_cost: float | None
    cooking_time_minutes: float | None
    cooking_sessions: int | None
    calories: float | None
    protein_grams: float | None
    fat_grams: float | None
    carbs_grams: float | None
    # (day index, meal type) -> normalized recipe name, for changed-meal counts.
    meal_slots: dict[tuple[int, str], str]


_HOURS_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*ч")
_MINUTES_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*мин")
_KCAL_PATTERN = re.compile(r"(\d+(?:[.,]\d+)?)\s*ккал")
_KBJU_PATTERNS = {
    "protein": re.compile(r"б\s*[:=]?\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE),
    "fat": re.compile(r"ж\s*[:=]?\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE),
    "carbs": re.compile(r"у\s*[:=]?\s*(\d+(?:[.,]\d+)?)", re.IGNORECASE),
}


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)) and math.isfinite(float(value)):
        return float(value)
    return None


def _to_float(raw: str) -> float:
    return float(raw.replace(",", "."))


def parse_cook_time_minutes(value: object) -> float | None:
    """Parses "30 мин", "1 ч", "1 ч 20 мин". Unknown formats return None."""
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().lower()
    hours = _HOURS_PATTERN.search(text)
    minutes = _MINUTES_PATTERN.search(text)
    if hours is None and minutes is None:
        return None
    total = 0.0
    if hours is not None:
        total += _to_float(hours.group(1)) * 60
    if minutes is not None:
        total += _to_float(minutes.group(1))
    return total


def parse_calories(value: object) -> float | None:
    """Parses "350 ккал" or a bare number string."""
    if isinstance(value, str) and value.strip():
        match = _KCAL_PATTERN.search(value.lower())
        if match is not None:
            return _to_float(match.group(1))
        bare = value.strip().replace(",", ".")
        try:
            return float(bare)
        except ValueError:
            return None
    return None


def parse_kbju(value: object) -> dict[str, float] | None:
    """Parses "Б:20г Ж:10г У:30г". All three components are required."""
    if not isinstance(value, str) or not value.strip():
        return None
    result: dict[str, float] = {}
    for key, pattern in _KBJU_PATTERNS.items():
        match = pattern.search(value)
        if match is None:
            return None
        result[key] = _to_float(match.group(1))
    return result


def _basket_cost(plan: dict[str, object]) -> float | None:
    basket = plan.get("basket")
    if not isinstance(basket, list) or not basket:
        return None
    total = 0.0
    for category in basket:
        if not isinstance(category, dict):
            return None
        items = category.get("items")
        if not isinstance(items, list):
            return None
        for item in items:
            if not isinstance(item, dict):
                return None
            price = _finite_number(item.get("price"))
            if price is None or price < 0:
                return None
            total += price
    return round(total, 2)


def _iter_meals(plan: dict[str, object]):
    days_plan = plan.get("days_plan")
    if not isinstance(days_plan, list):
        return
    for day_index, day in enumerate(days_plan):
        if not isinstance(day, dict):
            continue
        meals = day.get("meals")
        if not isinstance(meals, list):
            continue
        for meal in meals:
            if isinstance(meal, dict):
                yield day_index, meal


def _meal_slots(plan: dict[str, object]) -> dict[tuple[int, str], str]:
    slots: dict[tuple[int, str], str] = {}
    for day_index, meal in _iter_meals(plan):
        meal_type = meal.get("type")
        recipe_name = meal.get("recipe_name")
        if isinstance(meal_type, str) and isinstance(recipe_name, str):
            slots[(day_index, meal_type)] = recipe_name.strip().lower()
    return slots


def _cooking_sessions(plan: dict[str, object]) -> int | None:
    """Distinct cooking instances; falls back to requires_cooking counts.

    Plans without cooking metadata at all (legacy shapes) return None.
    """
    instance_ids: set[str] = set()
    requires_cooking_count = 0
    has_metadata = False
    for _day_index, meal in _iter_meals(plan):
        if "requires_cooking" in meal:
            has_metadata = True
        if meal.get("requires_cooking") is True:
            requires_cooking_count += 1
            instance_id = meal.get("cooking_instance_id")
            if isinstance(instance_id, str) and instance_id.strip():
                instance_ids.add(instance_id.strip())
    if not has_metadata:
        return None
    if instance_ids:
        return len(instance_ids)
    return requires_cooking_count


def _recipe_aggregates(
    plan: dict[str, object],
) -> tuple[float | None, float | None, dict[str, float] | None]:
    """(cooking minutes, calories, kbju) summed over recipes.

    Each aggregate is honest: if ANY recipe lacks parseable data for it, the
    whole aggregate is None. Consistent between original and current because
    both are computed by the same rules.
    """
    recipes = plan.get("recipes")
    if not isinstance(recipes, list) or not recipes:
        return None, None, None

    minutes_total: float | None = 0.0
    calories_total: float | None = 0.0
    kbju_total: dict[str, float] | None = {"protein": 0.0, "fat": 0.0, "carbs": 0.0}

    for recipe in recipes:
        if not isinstance(recipe, dict):
            return None, None, None
        minutes = parse_cook_time_minutes(recipe.get("cook_time"))
        if minutes is None:
            minutes_total = None
        elif minutes_total is not None:
            minutes_total += minutes
        calories = parse_calories(recipe.get("calories_per_portion"))
        if calories is None:
            calories_total = None
        elif calories_total is not None:
            calories_total += calories
        kbju = parse_kbju(recipe.get("kbju"))
        if kbju is None:
            kbju_total = None
        elif kbju_total is not None:
            for key in kbju_total:
                kbju_total[key] += kbju[key]

    return minutes_total, calories_total, kbju_total


def extract_characteristics(plan: dict[str, object]) -> PlanCharacteristics:
    total_cost = _finite_number(plan.get("total_cost"))
    if total_cost is not None and total_cost < 0:
        total_cost = None
    minutes, calories, kbju = _recipe_aggregates(plan)
    return PlanCharacteristics(
        total_cost=total_cost,
        basket_cost=_basket_cost(plan),
        cooking_time_minutes=minutes,
        cooking_sessions=_cooking_sessions(plan),
        calories=calories,
        protein_grams=kbju["protein"] if kbju is not None else None,
        fat_grams=kbju["fat"] if kbju is not None else None,
        carbs_grams=kbju["carbs"] if kbju is not None else None,
        meal_slots=_meal_slots(plan),
    )
