"""Deterministic reason codes for weekly strategy decisions."""

from __future__ import annotations

from dietary_constraints import DietaryConstraintKind
from strategy.context import ProfileContext
from strategy.effective_exclusions import has_legacy_exclusions
from strategy.models import WeeklyStrategy
from strategy.resolvers import BATCH_COOK_GOALS

PROFILE_ALLERGY_APPLIED = "PROFILE_ALLERGY_CONSTRAINTS_APPLIED"
PROFILE_INTOLERANCE_APPLIED = "PROFILE_INTOLERANCE_CONSTRAINTS_APPLIED"
PROFILE_PREFERENCE_APPLIED = "PROFILE_PREFERENCE_EXCLUSIONS_APPLIED"
PROFILE_LEGACY_APPLIED = "PROFILE_LEGACY_CONSTRAINTS_APPLIED"

_KIND_REASON_CODES: dict[str, str] = {
    DietaryConstraintKind.ALLERGY.value: PROFILE_ALLERGY_APPLIED,
    DietaryConstraintKind.INTOLERANCE.value: PROFILE_INTOLERANCE_APPLIED,
    DietaryConstraintKind.PREFERENCE.value: PROFILE_PREFERENCE_APPLIED,
}

GOAL_REASON_CODES: dict[str, str] = {
    "budget": "GOAL_BUDGET",
    "weightloss": "GOAL_WEIGHT_LOSS",
    "muscle": "GOAL_MUSCLE",
    "home": "GOAL_HOME",
    "healthy": "GOAL_HEALTHY",
    "restaurant": "GOAL_RESTAURANT",
}


def _all_cook_days(strategy: WeeklyStrategy) -> list[int]:
    return list(range(1, strategy.days + 1))


def collect_reason_codes(
    context: ProfileContext,
    strategy: WeeklyStrategy,
    *,
    memory_reason_codes: list[str] | None = None,
    behavior_reason_codes: list[str] | None = None,
    planning_reason_codes: list[str] | None = None,
) -> list[str]:
    """Collects reason codes recorded at strategy build time."""
    codes: list[str] = []

    if memory_reason_codes:
        codes.extend(memory_reason_codes)

    if behavior_reason_codes:
        codes.extend(behavior_reason_codes)

    if planning_reason_codes:
        codes.extend(planning_reason_codes)

    goal_code = GOAL_REASON_CODES.get(strategy.goal)
    if goal_code:
        codes.append(goal_code)

    all_days = _all_cook_days(strategy)
    if strategy.cook_days == all_days:
        if context.days <= 3 or context.cooktime == "fast":
            codes.append("COOK_DAYS_FAST_MODE")
        else:
            codes.append("COOK_DAYS_DAILY_VARIETY")
    else:
        codes.append("COOK_DAYS_REDUCE_DAILY_WORK")

    if strategy.leftovers_enabled:
        codes.append("LEFTOVERS_REDUCE_COOKING")
        if strategy.goal == "budget":
            codes.append("LEFTOVERS_SUPPORT_BUDGET")

    if strategy.repeat_breakfasts:
        codes.append("REPEAT_BREAKFASTS_SAVE_TIME")
    if strategy.repeat_lunches:
        codes.append("REPEAT_LUNCHES_SUPPORT_BATCH")
    if strategy.repeat_dinners:
        codes.append("REPEAT_DINNERS_SUPPORT_BUDGET")

    if len(strategy.shopping_days) == 1:
        codes.append("SHOPPING_DAYS_SINGLE_TRIP")
    else:
        codes.append("SHOPPING_DAYS_SPLIT_FRESH_PRODUCTS")

    if strategy.goal == "budget":
        codes.append("BUDGET_LIMITED_VARIETY")

    if strategy.cooking_time_limit <= 20:
        codes.append("COOKING_TIME_LIMIT_FAST")
    elif strategy.cooking_time_limit <= 45:
        codes.append("COOKING_TIME_LIMIT_MEDIUM")
    else:
        codes.append("COOKING_TIME_LIMIT_SLOW")

    proteins = strategy.preferred_proteins
    if proteins and proteins != ["any"] and len(proteins) > 1:
        codes.append("PROTEIN_ROTATION_FOR_VARIETY")

    if strategy.excluded_products:
        codes.append("EXCLUSIONS_APPLIED")

    for constraint in context.dietary_constraints:
        kind_code = _KIND_REASON_CODES.get(constraint.kind.value)
        if kind_code:
            codes.append(kind_code)
    if has_legacy_exclusions(context):
        codes.append(PROFILE_LEGACY_APPLIED)

    standard_meals = {"breakfast", "lunch", "dinner"}
    if set(strategy.meal_types) != standard_meals:
        codes.append("MEAL_TYPES_CUSTOM")

    return sorted(set(codes))


def infer_reason_codes(strategy: WeeklyStrategy) -> list[str]:
    """Infers reason codes from a persisted strategy snapshot (legacy records)."""
    codes: list[str] = []

    goal_code = GOAL_REASON_CODES.get(strategy.goal)
    if goal_code:
        codes.append(goal_code)

    all_days = _all_cook_days(strategy)
    if strategy.cook_days == all_days:
        if strategy.cooking_time_limit <= 20 or strategy.days <= 3:
            codes.append("COOK_DAYS_FAST_MODE")
        else:
            codes.append("COOK_DAYS_DAILY_VARIETY")
    elif strategy.goal in BATCH_COOK_GOALS:
        codes.append("COOK_DAYS_REDUCE_DAILY_WORK")
    else:
        codes.append("COOK_DAYS_REDUCE_DAILY_WORK")

    if strategy.leftovers_enabled:
        codes.append("LEFTOVERS_REDUCE_COOKING")
        if strategy.goal == "budget":
            codes.append("LEFTOVERS_SUPPORT_BUDGET")

    if strategy.repeat_breakfasts:
        codes.append("REPEAT_BREAKFASTS_SAVE_TIME")
    if strategy.repeat_lunches:
        codes.append("REPEAT_LUNCHES_SUPPORT_BATCH")
    if strategy.repeat_dinners:
        codes.append("REPEAT_DINNERS_SUPPORT_BUDGET")

    if len(strategy.shopping_days) == 1:
        codes.append("SHOPPING_DAYS_SINGLE_TRIP")
    else:
        codes.append("SHOPPING_DAYS_SPLIT_FRESH_PRODUCTS")

    if strategy.goal == "budget":
        codes.append("BUDGET_LIMITED_VARIETY")

    if strategy.cooking_time_limit <= 20:
        codes.append("COOKING_TIME_LIMIT_FAST")
    elif strategy.cooking_time_limit <= 45:
        codes.append("COOKING_TIME_LIMIT_MEDIUM")
    else:
        codes.append("COOKING_TIME_LIMIT_SLOW")

    proteins = strategy.preferred_proteins
    if proteins and proteins != ["any"] and len(proteins) > 1:
        codes.append("PROTEIN_ROTATION_FOR_VARIETY")

    if strategy.excluded_products:
        codes.append("EXCLUSIONS_APPLIED")

    standard_meals = {"breakfast", "lunch", "dinner"}
    if set(strategy.meal_types) != standard_meals:
        codes.append("MEAL_TYPES_CUSTOM")

    return sorted(set(codes))
