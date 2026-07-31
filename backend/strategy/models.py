"""Weekly strategy models for deterministic meal planning."""

from __future__ import annotations

import math
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from meal_types import VALID_MEAL_TYPES

GoalValue = Literal["healthy", "home", "muscle", "weightloss", "restaurant", "budget"]
ProteinValue = Literal[
    "chicken", "beef", "pork", "fish", "seafood", "eggs", "veggie", "any"
]
MealTypeValue = Literal["breakfast", "lunch", "dinner", "snack"]

VALID_GOALS: frozenset[str] = frozenset(
    {"healthy", "home", "muscle", "weightloss", "restaurant", "budget"}
)
VALID_PROTEINS: frozenset[str] = frozenset(
    {"chicken", "beef", "pork", "fish", "seafood", "eggs", "veggie", "any"}
)

DEFAULT_GOAL: GoalValue = "home"
DEFAULT_DAYS = 5
DEFAULT_BUDGET = 3000.0
DEFAULT_MEALS_PER_DAY = 3
DEFAULT_COOKING_TIME_LIMIT = 45
DEFAULT_PROTEINS: list[str] = ["any"]
DEFAULT_STRATEGY_VERSION = 5

# Day index semantics:
# - days: length of the planning period (e.g. 5 means five menu days)
# - cook_days / shopping_days: 1-based indices within that period (1..days inclusive)
# Example: days=5, cook_days=[1, 3, 5], shopping_days=[1, 4]


def _finite_positive_int(value: object, field_name: str, *, minimum: int = 1) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be an integer, not bool")
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    if value < minimum:
        raise ValueError(f"{field_name} must be >= {minimum}")
    return value


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


def _normalize_period_days(value: object, field_name: str) -> list[int]:
    if not isinstance(value, list) or len(value) == 0:
        raise ValueError(f"{field_name} must be a non-empty list")
    normalized: list[int] = []
    for item in value:
        day = _finite_positive_int(item, f"{field_name} item")
        if day not in normalized:
            normalized.append(day)
    return sorted(normalized)


class WeeklyStrategy(BaseModel):
    """Strategic decisions for a weekly meal plan. No menu or recipe data."""

    model_config = ConfigDict(extra="ignore")

    strategy_version: int = DEFAULT_STRATEGY_VERSION
    goal: GoalValue
    days: Annotated[int, Field(ge=1, le=14)]
    budget: Annotated[float, Field(ge=0)]
    meal_types: list[MealTypeValue]
    meals_per_day: Annotated[int, Field(ge=1, le=4)]
    cook_days: list[Annotated[int, Field(ge=1)]]
    shopping_days: list[Annotated[int, Field(ge=1)]]
    leftovers_enabled: bool
    repeat_breakfasts: bool
    repeat_lunches: bool
    repeat_dinners: bool
    preferred_proteins: list[ProteinValue]
    excluded_products: list[str]
    cooking_time_limit: Annotated[int, Field(ge=1)]
    prefer_faster_meals: bool = False
    availability_avoid_products: list[str] = Field(default_factory=list)
    prefer_familiar_meals: bool = False
    generated_at: str

    @field_validator("strategy_version", mode="before")
    @classmethod
    def validate_strategy_version(cls, value: object) -> int:
        if value is None:
            return DEFAULT_STRATEGY_VERSION
        return _finite_positive_int(value, "strategy_version")

    @field_validator("goal", mode="before")
    @classmethod
    def validate_goal(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("goal must be a string")
        normalized = value.strip().lower()
        if normalized not in VALID_GOALS:
            raise ValueError("goal is unknown")
        return normalized

    @field_validator("days", mode="before")
    @classmethod
    def validate_days(cls, value: object) -> int:
        return _finite_positive_int(value, "days")

    @field_validator("budget", mode="before")
    @classmethod
    def validate_budget(cls, value: object) -> float:
        return _finite_non_negative_number(value, "budget")

    @field_validator("meal_types", mode="before")
    @classmethod
    def validate_meal_types(cls, value: object) -> list[str]:
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError("meal_types must be a non-empty list")

        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                raise ValueError("meal_types items must be strings")
            meal_type = item.strip().lower()
            if meal_type in normalized:
                raise ValueError("meal_types must not contain duplicates")
            if meal_type not in VALID_MEAL_TYPES:
                raise ValueError("meal_types contains unknown value")
            normalized.append(meal_type)

        return normalized

    @field_validator("meals_per_day", mode="before")
    @classmethod
    def validate_meals_per_day(cls, value: object) -> int:
        return _finite_positive_int(value, "meals_per_day", minimum=1)

    @field_validator("cook_days", mode="before")
    @classmethod
    def validate_cook_days(cls, value: object) -> list[int]:
        return _normalize_period_days(value, "cook_days")

    @field_validator("shopping_days", mode="before")
    @classmethod
    def validate_shopping_days(cls, value: object) -> list[int]:
        return _normalize_period_days(value, "shopping_days")

    @field_validator("preferred_proteins", mode="before")
    @classmethod
    def validate_preferred_proteins(cls, value: object) -> list[str]:
        if not isinstance(value, list) or len(value) == 0:
            raise ValueError("preferred_proteins must be a non-empty list")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            protein = item.strip().lower()
            if not protein:
                continue
            if protein not in VALID_PROTEINS:
                raise ValueError("preferred_proteins contains unknown value")
            if protein not in normalized:
                normalized.append(protein)
        if not normalized:
            raise ValueError("preferred_proteins must contain at least one valid protein")
        return normalized

    @field_validator("excluded_products", mode="before")
    @classmethod
    def validate_excluded_products(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("excluded_products must be a list")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            stripped = item.strip()
            if stripped and stripped not in normalized:
                normalized.append(stripped)
        return normalized

    @field_validator("cooking_time_limit", mode="before")
    @classmethod
    def validate_cooking_time_limit(cls, value: object) -> int:
        return _finite_positive_int(value, "cooking_time_limit")

    @field_validator("availability_avoid_products", mode="before")
    @classmethod
    def validate_availability_avoid_products(cls, value: object) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ValueError("availability_avoid_products must be a list")
        normalized: list[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            stripped = item.strip()
            if stripped and stripped not in normalized:
                normalized.append(stripped)
        return normalized

    @field_validator("generated_at", mode="before")
    @classmethod
    def validate_generated_at(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("generated_at must be a non-empty ISO timestamp string")
        return value.strip()

    @model_validator(mode="after")
    def validate_internal_consistency(self) -> "WeeklyStrategy":
        if len(self.meal_types) != len(set(self.meal_types)):
            raise ValueError("meal_types must not contain duplicates")

        if self.meals_per_day != len(self.meal_types):
            raise ValueError("meals_per_day must equal len(meal_types)")

        valid_period = set(range(1, self.days + 1))

        for day in self.cook_days:
            if day not in valid_period:
                raise ValueError(
                    f"cook_days value {day} is outside planning period 1..{self.days}"
                )

        for day in self.shopping_days:
            if day not in valid_period:
                raise ValueError(
                    f"shopping_days value {day} is outside planning period 1..{self.days}"
                )

        return self

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, payload: str) -> "WeeklyStrategy":
        return cls.model_validate_json(payload)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "WeeklyStrategy":
        return cls.model_validate(payload)
