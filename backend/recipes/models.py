"""In-memory domain models for Recipe Catalog (loaded from SQLite)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from recipes.enums import (
    BudgetClass,
    CookingMethod,
    Difficulty,
    EnergyDensity,
    EquipmentType,
    FiberLevel,
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


@dataclass(frozen=True)
class IngredientAlias:
    id: str
    ingredient_id: str
    alias: str
    normalized_alias: str


@dataclass(frozen=True)
class Ingredient:
    id: str
    canonical_name: str
    display_name: str
    category: str
    default_unit: IngredientUnit
    piece_weight_g: float | None
    density_g_per_ml: float | None
    is_pantry_staple: bool
    aliases: tuple[IngredientAlias, ...] = ()
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class RecipeIngredient:
    id: str
    recipe_id: str
    ingredient_id: str
    quantity: Decimal
    unit: IngredientUnit
    quantity_grams: Decimal | None
    preparation: str | None
    is_optional: bool
    ingredient_group: IngredientGroup
    sort_order: int
    scaling_factor: Decimal
    rounding_increment: Decimal | None
    ingredient: Ingredient | None = None


@dataclass(frozen=True)
class RecipeStep:
    id: str
    recipe_id: str
    step_number: int
    instruction: str
    duration_minutes: int | None
    active_minutes: int | None
    temperature_c: int | None
    ingredient_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RecipeEquipmentItem:
    equipment: EquipmentType
    required: bool


@dataclass(frozen=True)
class RecipeRoleItem:
    role: RecipeRole
    score: float
    reason: str | None


@dataclass(frozen=True)
class RecipeGoalScore:
    goal: GoalType
    score: float
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class RecipeTag:
    tag_type: TagType
    tag_value: str


@dataclass(frozen=True)
class RecipeMealTypeLink:
    meal_type: MealType
    is_primary: bool


@dataclass(frozen=True)
class RecipeRelation:
    id: str
    source_recipe_id: str
    target_recipe_id: str
    relation_type: RelationType
    score: float
    reason: str | None
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class Recipe:
    id: str
    slug: str
    name: str
    description: str
    status: RecipeStatus
    version: int
    primary_meal_type: MealType
    base_servings: Decimal
    yield_weight_g: Decimal
    recommended_portion_min_g: Decimal
    recommended_portion_max_g: Decimal
    scaling_mode: ScalingMode
    min_batch_servings: Decimal
    max_batch_servings: Decimal
    prep_time_minutes: int
    cook_time_minutes: int
    active_time_minutes: int
    total_time_minutes: int
    difficulty: Difficulty
    requires_cooking: bool
    batch_friendly: bool
    leftover_friendly: bool
    storage_days: int | None
    freezing_supported: bool
    budget_class: BudgetClass
    energy_density: EnergyDensity
    protein_level: ProteinLevel
    fiber_level: FiberLevel
    satiety_level: SatietyLevel
    calories_per_100g: float
    protein_g_per_100g: float
    fat_g_per_100g: float
    carbs_g_per_100g: float
    image_key: str | None
    created_at: str
    updated_at: str
    meal_types: tuple[RecipeMealTypeLink, ...] = ()
    ingredients: tuple[RecipeIngredient, ...] = ()
    steps: tuple[RecipeStep, ...] = ()
    cooking_methods: tuple[CookingMethod, ...] = ()
    equipment: tuple[RecipeEquipmentItem, ...] = ()
    roles: tuple[RecipeRoleItem, ...] = ()
    goal_scores: tuple[RecipeGoalScore, ...] = ()
    tags: tuple[RecipeTag, ...] = ()


@dataclass
class ScaledRecipeIngredient:
    recipe_ingredient_id: str
    ingredient_id: str
    quantity: Decimal
    unit: IngredientUnit
    quantity_grams: Decimal | None
    is_optional: bool
    ingredient_group: IngredientGroup
    sort_order: int
    display_name: str | None = None


@dataclass
class ScaledRecipe:
    recipe_id: str
    base_servings: Decimal
    target_servings: Decimal
    ingredients: list[ScaledRecipeIngredient] = field(default_factory=list)
