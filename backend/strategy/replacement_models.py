"""Pydantic models for replace-meal API and LLM response."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from memory.constants import MAX_EVENT_KEY_LENGTH, MAX_TARGET_LENGTH, VALID_REASON_CODES
from menu_models import DayMeal, MenuPlan, Recipe
from strategy.replacement_constants import MAX_REASON_LENGTH


class ReplaceMealRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    strategy_id: str
    menu_plan: MenuPlan
    meal_id: str
    reason: str | None = None
    # Sprint 5.13 — structured feedback (all optional; legacy requests still work).
    reason_code: str | None = None
    target_ingredient: str | None = None
    replacement_request_id: str | None = None
    # Sprint 7.2 — durable plan identity (optional; legacy plans have neither).
    menu_plan_id: str | None = Field(default=None, max_length=80)
    expected_revision: int | None = Field(default=None, ge=1)

    @field_validator("menu_plan_id", mode="before")
    @classmethod
    def validate_menu_plan_id(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("menu_plan_id must be a string")
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_durable_identity(self) -> "ReplaceMealRequest":
        if self.menu_plan_id is not None and self.expected_revision is None:
            raise ValueError("expected_revision is required with menu_plan_id")
        return self

    @field_validator("strategy_id", "meal_id", mode="before")
    @classmethod
    def validate_non_empty_id(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("ID must be a string")
        stripped = value.strip()
        if not stripped:
            raise ValueError("ID must not be empty")
        return stripped

    @field_validator("reason", mode="before")
    @classmethod
    def validate_reason(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("reason must be a string")
        stripped = value.strip()
        if not stripped:
            return None
        if len(stripped) > MAX_REASON_LENGTH:
            raise ValueError(f"reason must be at most {MAX_REASON_LENGTH} characters")
        return stripped

    @field_validator("reason_code", mode="before")
    @classmethod
    def validate_reason_code(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("reason_code must be a string")
        stripped = value.strip()
        if not stripped:
            return None
        if stripped not in VALID_REASON_CODES:
            raise ValueError("reason_code is not a recognized value")
        return stripped

    @field_validator("target_ingredient", mode="before")
    @classmethod
    def validate_target_ingredient(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("target_ingredient must be a string")
        stripped = value.strip()
        if not stripped:
            return None
        if len(stripped) > MAX_TARGET_LENGTH:
            raise ValueError(f"target_ingredient must be at most {MAX_TARGET_LENGTH} characters")
        return stripped

    @field_validator("replacement_request_id", mode="before")
    @classmethod
    def validate_replacement_request_id(cls, value: object) -> str | None:
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError("replacement_request_id must be a string")
        stripped = value.strip()
        if not stripped:
            return None
        if len(stripped) > MAX_EVENT_KEY_LENGTH:
            raise ValueError("replacement_request_id is too long")
        return stripped


class MealReplacementItem(BaseModel):
    model_config = ConfigDict(extra="ignore")

    meal: DayMeal
    recipe: Recipe


class ReplacementLLMResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    replacement: MealReplacementItem
    affected_meals: list[MealReplacementItem] = Field(default_factory=list)


class ReplaceMealResponse(BaseModel):
    menu_plan: MenuPlan
    replaced_meal_id: str
    changed_meal_ids: list[str]
    # Optional, non-authoritative memory side-effect metadata (Sprint 5.13).
    # Frontend must not depend on this to update the MenuPlan.
    memory: dict | None = None
    # Sprint 7.2 — durable plan identity of the appended revision.
    # Null for legacy plans that were never persisted server-side.
    menu_plan_id: str | None = None
    revision: int | None = None
