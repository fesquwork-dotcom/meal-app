"""Pydantic schemas for Recipe Catalog YAML/JSON files and in-memory validation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from recipes.enums import (
    TAG_VALUE_REGISTRY,
    BudgetClass,
    CookingMethod,
    Difficulty,
    EnergyDensity,
    EquipmentType,
    FiberLevel,
    GoalReasonCode,
    GoalType,
    IngredientGroup,
    IngredientUnit,
    MealType,
    ProteinLevel,
    RecipeRole,
    RecipeStatus,
    RelationType,
    SatietyLevel,
    ScalingMode,
    TagType,
)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class IngredientAliasSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: str = Field(min_length=1)


class IngredientSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    canonical_name: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    default_unit: IngredientUnit
    piece_weight_g: float | None = None
    density_g_per_ml: float | None = None
    is_pantry_staple: bool = False
    aliases: list[str] = Field(default_factory=list)


class RecipeMealTypeSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    meal_type: MealType
    is_primary: bool = False


class RecipeIngredientSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    ingredient_id: str = Field(min_length=1)
    quantity: float = Field(gt=0)
    unit: IngredientUnit
    quantity_grams: float | None = Field(default=None, gt=0)
    preparation: str | None = None
    is_optional: bool = False
    ingredient_group: IngredientGroup = IngredientGroup.MAIN
    sort_order: int = Field(ge=1)
    scaling_factor: float = Field(default=1.0, gt=0)
    rounding_increment: float | None = Field(default=None, gt=0)


class RecipeStepSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    step_number: int = Field(ge=1)
    instruction: str = Field(min_length=1)
    duration_minutes: int | None = Field(default=None, ge=0)
    active_minutes: int | None = Field(default=None, ge=0)
    temperature_c: int | None = None
    ingredient_refs: list[str] = Field(
        default_factory=list,
        description="recipe_ingredient ids or sort_order keys used in file",
    )

    @model_validator(mode="after")
    def _active_le_duration(self) -> RecipeStepSchema:
        if (
            self.active_minutes is not None
            and self.duration_minutes is not None
            and self.active_minutes > self.duration_minutes
        ):
            raise ValueError("active_minutes must be <= duration_minutes")
        return self


class RecipeEquipmentSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    equipment: EquipmentType
    required: bool = True


class RecipeRoleSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: RecipeRole
    score: float = Field(ge=0, le=1)
    reason: str | None = None


class RecipeGoalScoreSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: GoalType
    score: float = Field(ge=0, le=1)
    reason_codes: list[GoalReasonCode] = Field(default_factory=list)


class RecipeTagSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag_type: TagType
    tag_value: str = Field(min_length=1)

    @model_validator(mode="after")
    def _closed_tag_value(self) -> RecipeTagSchema:
        allowed = TAG_VALUE_REGISTRY.get(self.tag_type)
        if allowed is not None and self.tag_value not in allowed:
            raise ValueError(
                f"Unknown tag_value '{self.tag_value}' for tag_type '{self.tag_type}'"
            )
        return self


class RecipeCardSchema(BaseModel):
    """Full recipe file payload."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    slug: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: RecipeStatus = RecipeStatus.ACTIVE
    version: int = Field(default=1, ge=1)
    primary_meal_type: MealType
    meal_types: list[RecipeMealTypeSchema] = Field(min_length=1)
    base_servings: float = Field(gt=0)
    yield_weight_g: float = Field(gt=0)
    recommended_portion_min_g: float = Field(gt=0)
    recommended_portion_max_g: float = Field(gt=0)
    scaling_mode: ScalingMode
    min_batch_servings: float = Field(gt=0)
    max_batch_servings: float = Field(gt=0)
    prep_time_minutes: int = Field(ge=0)
    cook_time_minutes: int = Field(ge=0)
    active_time_minutes: int = Field(ge=0)
    total_time_minutes: int = Field(ge=0)
    difficulty: Difficulty
    requires_cooking: bool
    batch_friendly: bool = False
    leftover_friendly: bool = False
    storage_days: int | None = Field(default=None, ge=0)
    freezing_supported: bool = False
    budget_class: BudgetClass
    energy_density: EnergyDensity
    protein_level: ProteinLevel
    fiber_level: FiberLevel
    satiety_level: SatietyLevel
    calories_per_100g: float = Field(ge=0)
    protein_g_per_100g: float = Field(ge=0)
    fat_g_per_100g: float = Field(ge=0)
    carbs_g_per_100g: float = Field(ge=0)
    image_key: str | None = None
    ingredients: list[RecipeIngredientSchema] = Field(min_length=1)
    steps: list[RecipeStepSchema] = Field(min_length=1)
    cooking_methods: list[CookingMethod] = Field(min_length=1)
    equipment: list[RecipeEquipmentSchema] = Field(default_factory=list)
    roles: list[RecipeRoleSchema] = Field(default_factory=list)
    goal_scores: list[RecipeGoalScoreSchema] = Field(default_factory=list)
    tags: list[RecipeTagSchema] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistency(self) -> RecipeCardSchema:
        if self.recommended_portion_max_g < self.recommended_portion_min_g:
            raise ValueError("recommended_portion_max_g < min")
        if self.max_batch_servings < self.min_batch_servings:
            raise ValueError("max_batch_servings < min_batch_servings")
        if not (
            self.min_batch_servings <= self.base_servings <= self.max_batch_servings
        ):
            raise ValueError("base_servings outside batch range")
        if self.total_time_minutes < self.prep_time_minutes:
            raise ValueError("total_time_minutes < prep_time_minutes")
        if self.total_time_minutes < self.cook_time_minutes:
            raise ValueError("total_time_minutes < cook_time_minutes")
        if self.total_time_minutes < self.active_time_minutes:
            raise ValueError("total_time_minutes < active_time_minutes")

        primaries = [m for m in self.meal_types if m.is_primary]
        if len(primaries) != 1:
            raise ValueError("exactly one meal_type must be primary")
        if primaries[0].meal_type != self.primary_meal_type:
            raise ValueError("primary meal_type mismatch")

        sorts = [i.sort_order for i in self.ingredients]
        if len(sorts) != len(set(sorts)):
            raise ValueError("duplicate ingredient sort_order")

        step_nums = sorted(s.step_number for s in self.steps)
        if step_nums != list(range(1, len(step_nums) + 1)):
            raise ValueError("step_number must be contiguous starting at 1")

        if self.status == RecipeStatus.ACTIVE and not self.cooking_methods:
            raise ValueError("active recipe requires cooking methods")

        goals = [g.goal for g in self.goal_scores]
        if len(goals) != len(set(goals)):
            raise ValueError("duplicate goal scores")

        return self


class RecipeRelationSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    source_recipe_id: str = Field(min_length=1)
    target_recipe_id: str = Field(min_length=1)
    relation_type: RelationType
    score: float = Field(ge=0, le=1)
    reason: str | None = None
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _no_self(self) -> RecipeRelationSchema:
        if self.source_recipe_id == self.target_recipe_id:
            raise ValueError("relation source cannot equal target")
        return self


class IngredientsFileSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingredients: list[IngredientSchema]


class RelationsFileSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    relations: list[RecipeRelationSchema]


def reason_codes_to_json(codes: list[GoalReasonCode]) -> str:
    return json.dumps([c.value for c in codes], ensure_ascii=False)


def parse_reason_codes_json(raw: str | None) -> list[str]:
    if not raw:
        return []
    data = json.loads(raw)
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]
