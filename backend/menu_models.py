"""Pydantic models for normalized menu plan API contract."""

from __future__ import annotations

import math
import re
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

MealTypeValue = Literal["breakfast", "lunch", "dinner", "snack"]


def _strip_required(value: object, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    stripped = value.strip()
    if not stripped:
        raise ValueError(f"{field_name} must not be empty")
    return stripped


def _finite_non_negative_number(value: object, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a number, not bool")
    if not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    numeric = float(value)
    if not math.isfinite(numeric):
        raise ValueError(f"{field_name} must be finite")
    if numeric < 0:
        raise ValueError(f"{field_name} must be >= 0")
    return numeric


def _normalize_cook_time(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        raise ValueError("cook_time must not be bool")
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError("cook_time must be finite")
        return f"{int(value)} мин"
    if isinstance(value, str):
        return value.strip()
    raise ValueError("cook_time must be string or number")


def _normalize_kbju(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        raise ValueError("kbju must not be bool")
    if isinstance(value, (int, float)):
        if not math.isfinite(float(value)):
            raise ValueError("kbju must be finite")
        return str(value)
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return " · ".join(f"{key}: {item}" for key, item in value.items())
    return ""


ContributionValue = Literal["purchase", "from_source", "pantry"]


class RecipeIngredient(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    amount: str = ""
    contribution: ContributionValue | None = None

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return _strip_required(value, "ingredient.name")

    @field_validator("amount", mode="before")
    @classmethod
    def validate_amount(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return str(value)
        return ""

    @field_validator("contribution", mode="before")
    @classmethod
    def validate_contribution(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("ingredient.contribution must be a string")
        normalized = value.strip().lower()
        if normalized not in {"purchase", "from_source", "pantry"}:
            raise ValueError("ingredient.contribution is invalid")
        return normalized


class IngredientSubstitute(BaseModel):
    """Optional AI/presentation substitute pair. Empty when absent."""

    model_config = ConfigDict(extra="ignore")

    original: str
    replacement: str

    @field_validator("original", "replacement", mode="before")
    @classmethod
    def validate_label(cls, value: object) -> str:
        return _strip_required(value, "substitute")


class Recipe(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    recipe_id: str | None = None
    emoji: str = "🍽"
    cook_time: str = ""
    kbju: str = ""
    ingredients: list[RecipeIngredient]
    steps: list[str]
    difficulty: str | None = None
    calories_per_portion: str | None = None
    description: str | None = None
    # Presentation-only optional fields (never required; hide UI when empty).
    tips: list[str] = Field(default_factory=list)
    substitutes: list[IngredientSubstitute] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return _strip_required(value, "recipe.name")

    @field_validator("recipe_id", mode="before")
    @classmethod
    def validate_recipe_id(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("recipe.recipe_id must be a string")
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    @field_validator("emoji", mode="before")
    @classmethod
    def validate_emoji(cls, value: object) -> str:
        if value is None:
            return "🍽"
        if isinstance(value, str) and value.strip():
            return value.strip()
        return "🍽"

    @field_validator("cook_time", mode="before")
    @classmethod
    def validate_cook_time(cls, value: object) -> str:
        return _normalize_cook_time(value)

    @field_validator("kbju", mode="before")
    @classmethod
    def validate_kbju(cls, value: object) -> str:
        return _normalize_kbju(value)

    @field_validator("ingredients", mode="before")
    @classmethod
    def validate_ingredients(cls, value: object) -> list[RecipeIngredient]:
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError("recipe.ingredients must be a non-empty list")
        return value

    @field_validator("steps", mode="before")
    @classmethod
    def validate_steps(cls, value: object) -> list[str]:
        if not isinstance(value, list):
            raise ValueError("recipe.steps must be a list")
        cleaned = [item.strip() for item in value if isinstance(item, str) and item.strip()]
        if not cleaned:
            raise ValueError("recipe.steps must contain non-empty strings")
        return cleaned

    @field_validator("tips", mode="before")
    @classmethod
    def validate_tips(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]

    @field_validator("substitutes", mode="before")
    @classmethod
    def validate_substitutes(cls, value: object) -> list[IngredientSubstitute]:
        if value is None or value == []:
            return []
        if not isinstance(value, list):
            return []
        cleaned: list[IngredientSubstitute] = []
        for item in value:
            if isinstance(item, IngredientSubstitute):
                cleaned.append(item)
                continue
            if not isinstance(item, dict):
                continue
            original = item.get("original") or item.get("from") or item.get("ingredient")
            replacement = item.get("replacement") or item.get("to") or item.get("substitute")
            if not isinstance(original, str) or not isinstance(replacement, str):
                continue
            if not original.strip() or not replacement.strip():
                continue
            cleaned.append(
                IngredientSubstitute(original=original.strip(), replacement=replacement.strip())
            )
        return cleaned


class DayMeal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    type: MealTypeValue
    recipe_name: str
    recipe_id: str | None = None
    meal_id: str | None = None
    requires_cooking: bool | None = None
    prepared_on_day: int | None = None
    uses_leftovers: bool = False
    source_meal_id: str | None = None
    cooking_instance_id: str | None = None

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("meal.type must be a string")
        normalized = value.strip().lower()
        if normalized not in {"breakfast", "lunch", "dinner", "snack"}:
            raise ValueError("meal.type is unknown")
        return normalized

    @field_validator("recipe_name", mode="before")
    @classmethod
    def validate_recipe_name(cls, value: object) -> str:
        return _strip_required(value, "meal.recipe_name")

    @field_validator("recipe_id", mode="before")
    @classmethod
    def validate_recipe_id(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("meal.recipe_id must be a string")
        stripped = value.strip()
        if not stripped:
            return None
        return stripped

    @field_validator("meal_id", mode="before")
    @classmethod
    def validate_meal_id(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("meal.meal_id must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("meal.meal_id must not be empty")
        return stripped

    @field_validator("prepared_on_day", mode="before")
    @classmethod
    def validate_prepared_on_day(cls, value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("meal.prepared_on_day must be an integer, not bool")
        if not isinstance(value, int):
            raise ValueError("meal.prepared_on_day must be an integer")
        if value < 1:
            raise ValueError("meal.prepared_on_day must be >= 1")
        return value

    @field_validator("source_meal_id", mode="before")
    @classmethod
    def validate_source_meal_id(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("meal.source_meal_id must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("meal.source_meal_id must not be empty")
        return stripped

    @field_validator("cooking_instance_id", mode="before")
    @classmethod
    def validate_cooking_instance_id(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("meal.cooking_instance_id must be a string")
        stripped = value.strip()
        if not stripped:
            return None
        return stripped


class DayPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    day: str
    meals: list[DayMeal]
    breakfast: str = ""
    lunch: str = ""
    dinner: str = ""

    @field_validator("day", mode="before")
    @classmethod
    def validate_day(cls, value: object) -> str:
        return _strip_required(value, "day")

    @field_validator("meals", mode="before")
    @classmethod
    def validate_meals(cls, value: object) -> list[DayMeal]:
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError("day.meals must be a non-empty list")
        return value

    @model_validator(mode="after")
    def sync_legacy_slots(self) -> "DayPlan":
        legacy = {"breakfast": "", "lunch": "", "dinner": ""}
        for meal in self.meals:
            if meal.type in legacy:
                legacy[meal.type] = meal.recipe_name
        self.breakfast = legacy["breakfast"]
        self.lunch = legacy["lunch"]
        self.dinner = legacy["dinner"]
        return self


class BasketItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str
    weight: str = ""
    price: Annotated[float, Field(ge=0)]
    # Presentation enrichment (optional; legacy baskets omit these).
    used_in_recipes: int | None = None
    shopping_advice: list[str] = Field(default_factory=list)
    badges: list[str] = Field(default_factory=list)

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, value: object) -> str:
        return _strip_required(value, "basket item.name")

    @field_validator("weight", mode="before")
    @classmethod
    def validate_weight(cls, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, (int, float)) and math.isfinite(float(value)):
            return str(value)
        return ""

    @field_validator("price", mode="before")
    @classmethod
    def validate_price(cls, value: object) -> float:
        return _finite_non_negative_number(value, "basket item.price")

    @field_validator("used_in_recipes", mode="before")
    @classmethod
    def validate_used_in_recipes(cls, value: object) -> int | None:
        if value is None:
            return None
        if isinstance(value, bool):
            raise ValueError("used_in_recipes must be an integer, not bool")
        if isinstance(value, int) and value >= 1:
            return value
        if isinstance(value, float) and math.isfinite(value) and int(value) == value and value >= 1:
            return int(value)
        return None

    @field_validator("shopping_advice", "badges", mode="before")
    @classmethod
    def validate_string_list(cls, value: object) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            stripped = value.strip()
            return [stripped] if stripped else []
        if not isinstance(value, list):
            return []
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]


class BasketCategory(BaseModel):
    model_config = ConfigDict(extra="ignore")

    category: str
    items: list[BasketItem]

    @field_validator("category", mode="before")
    @classmethod
    def validate_category(cls, value: object) -> str:
        return _strip_required(value, "basket.category")

    @field_validator("items", mode="before")
    @classmethod
    def validate_items(cls, value: object) -> list[BasketItem]:
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError("basket category items must be a non-empty list")
        return value


class MenuPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")

    summary: str
    plan_start_date: date | None = None
    strategy_id: str | None = None
    total_cost: Annotated[float, Field(ge=0)]
    days_plan: list[DayPlan]
    recipes: list[Recipe]
    basket: list[BasketCategory]
    # Sprint 10.11: catalog planner observability (optional; None for legacy Claude).
    generation_engine: str | None = None
    planner_score: float | None = None
    planner_version: str | None = None
    planning_duration_ms: float | None = None

    @field_validator("summary", mode="before")
    @classmethod
    def validate_summary(cls, value: object) -> str:
        return _strip_required(value, "summary")

    @field_validator("total_cost", mode="before")
    @classmethod
    def validate_total_cost(cls, value: object) -> float:
        return _finite_non_negative_number(value, "total_cost")

    @field_validator("days_plan", mode="before")
    @classmethod
    def validate_days_plan(cls, value: object) -> list[DayPlan]:
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError("days_plan must be a non-empty list")
        return value

    @field_validator("recipes", mode="before")
    @classmethod
    def validate_recipes(cls, value: object) -> list[Recipe]:
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError("recipes must be a non-empty list")
        return value

    @field_validator("basket", mode="before")
    @classmethod
    def validate_basket(cls, value: object) -> list[BasketCategory]:
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError("basket must be a non-empty list")
        return value


_MEAL_PREFIX_PATTERN = re.compile(r"^(завтрак|обед|ужин|перекус)\s*:?\s*", re.IGNORECASE)
_PUNCTUATION_PATTERN = re.compile(r"[.,!?;:()\[\]«»\"'']")


def normalize_meal_name(name: str) -> str:
    """Backend analogue of frontend normalizeMealName for meal-recipe matching."""
    normalized = name.strip().lower().replace("ё", "е")
    normalized = _PUNCTUATION_PATTERN.sub(" ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    normalized = _MEAL_PREFIX_PATTERN.sub("", normalized).strip()
    return normalized
