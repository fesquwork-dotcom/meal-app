"""Recipe Catalog domain enums (Sprint 10.4).

MealType values match backend.meal_types.VALID_MEAL_TYPES (Literal-based).
Catalog uses StrEnum for closed sets; generation MenuPlan models are unchanged.
"""

from __future__ import annotations

from enum import StrEnum

from meal_types import VALID_MEAL_TYPES


class RecipeStatus(StrEnum):
    DRAFT = "draft"
    VALIDATED = "validated"
    ACTIVE = "active"
    ARCHIVED = "archived"


class MealType(StrEnum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    SNACK = "snack"


assert set(MealType) <= VALID_MEAL_TYPES


class Difficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ScalingMode(StrEnum):
    LINEAR = "linear"
    DISCRETE = "discrete"
    LIMITED = "limited"


class BudgetClass(StrEnum):
    VERY_BUDGET = "very_budget"
    BUDGET = "budget"
    STANDARD = "standard"
    PREMIUM = "premium"


class EnergyDensity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProteinLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FiberLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SatietyLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RecipeRole(StrEnum):
    QUICK_MEAL = "quick_meal"
    MAIN_COOK = "main_cook"
    BATCH_BASE = "batch_base"
    LEFTOVER_SOURCE = "leftover_source"
    LEFTOVER_MEAL = "leftover_meal"
    LIGHT_MEAL = "light_meal"
    PORTABLE_MEAL = "portable_meal"
    WEEKEND_MEAL = "weekend_meal"
    FAMILY_MEAL = "family_meal"


class GoalType(StrEnum):
    BALANCED = "balanced"
    WEIGHT_LOSS = "weight_loss"
    WEIGHT_MAINTENANCE = "weight_maintenance"
    MUSCLE_GAIN = "muscle_gain"
    BUDGET = "budget"
    QUICK_COOKING = "quick_cooking"
    FAMILY = "family"


class RelationType(StrEnum):
    SHARES_INGREDIENTS = "shares_ingredients"
    USES_LEFTOVERS_FROM = "uses_leftovers_from"
    PROVIDES_COMPONENT_FOR = "provides_component_for"
    GOOD_PAIR = "good_pair"
    BALANCES_NUTRITION = "balances_nutrition"
    AVOID_SAME_DAY = "avoid_same_day"
    AVOID_CONSECUTIVE_DAYS = "avoid_consecutive_days"
    SIMILAR_MEAL = "similar_meal"


class CookingMethod(StrEnum):
    NO_COOK = "no_cook"
    BOILING = "boiling"
    STEWING = "stewing"
    FRYING = "frying"
    BAKING = "baking"
    ROASTING = "roasting"
    STEAMING = "steaming"
    SLOW_COOKING = "slow_cooking"


class EquipmentType(StrEnum):
    STOVE = "stove"
    OVEN = "oven"
    MICROWAVE = "microwave"
    FRYING_PAN = "frying_pan"
    POT = "pot"
    SAUCEPAN = "saucepan"
    BAKING_DISH = "baking_dish"
    BLENDER = "blender"
    GRATER = "grater"
    KNIFE = "knife"
    CUTTING_BOARD = "cutting_board"


class IngredientUnit(StrEnum):
    G = "g"
    ML = "ml"
    PIECE = "piece"
    TSP = "tsp"
    TBSP = "tbsp"


class IngredientGroup(StrEnum):
    MAIN = "main"
    SAUCE = "sauce"
    GARNISH = "garnish"
    TOPPING = "topping"
    SEASONING = "seasoning"


class TagType(StrEnum):
    PROTEIN_SOURCE = "protein_source"
    CUISINE = "cuisine"
    TEXTURE = "texture"
    TASTE = "taste"
    USAGE = "usage"
    DIETARY = "dietary"


class ProteinSourceTag(StrEnum):
    CHICKEN = "chicken"
    TURKEY = "turkey"
    BEEF = "beef"
    PORK = "pork"
    FISH = "fish"
    EGGS = "eggs"
    DAIRY = "dairy"
    LEGUMES = "legumes"
    MIXED = "mixed"
    NONE = "none"


class CuisineTag(StrEnum):
    RUSSIAN = "russian"
    EUROPEAN = "european"
    MEDITERRANEAN = "mediterranean"
    ASIAN = "asian"
    INTERNATIONAL = "international"


class TextureTag(StrEnum):
    SOFT = "soft"
    CREAMY = "creamy"
    CRISPY = "crispy"
    LIQUID = "liquid"
    CHUNKY = "chunky"
    BAKED = "baked"


class TasteTag(StrEnum):
    NEUTRAL = "neutral"
    SAVORY = "savory"
    SWEET = "sweet"
    MILD = "mild"
    SPICY = "spicy"


class UsageTag(StrEnum):
    QUICK = "quick"
    MEAL_PREP = "meal_prep"
    LUNCHBOX = "lunchbox"
    FAMILY = "family"
    FREEZER_FRIENDLY = "freezer_friendly"


class DietaryTag(StrEnum):
    VEGETARIAN = "vegetarian"
    PESCATARIAN = "pescatarian"
    GLUTEN_FREE = "gluten_free"
    LACTOSE_FREE = "lactose_free"


class GoalReasonCode(StrEnum):
    HIGH_PROTEIN = "HIGH_PROTEIN"
    MODERATE_CALORIES = "MODERATE_CALORIES"
    LOW_ENERGY_DENSITY = "LOW_ENERGY_DENSITY"
    HIGH_SATIETY = "HIGH_SATIETY"
    HIGH_FIBER = "HIGH_FIBER"
    BUDGET_FRIENDLY = "BUDGET_FRIENDLY"
    QUICK_PREPARATION = "QUICK_PREPARATION"
    FAMILY_FRIENDLY = "FAMILY_FRIENDLY"
    EASY_PORTION_SCALING = "EASY_PORTION_SCALING"
    BATCH_FRIENDLY = "BATCH_FRIENDLY"
    LEFTOVER_FRIENDLY = "LEFTOVER_FRIENDLY"


TAG_VALUE_REGISTRY: dict[TagType, frozenset[str]] = {
    TagType.PROTEIN_SOURCE: frozenset(ProteinSourceTag),
    TagType.CUISINE: frozenset(CuisineTag),
    TagType.TEXTURE: frozenset(TextureTag),
    TagType.TASTE: frozenset(TasteTag),
    TagType.USAGE: frozenset(UsageTag),
    TagType.DIETARY: frozenset(DietaryTag),
}
