"""Weekly planner reason / violation codes (separate from Selector codes)."""

from __future__ import annotations

from enum import StrEnum


class PlannerReasonCode(StrEnum):
    SELECTOR_QUALITY = "SELECTOR_QUALITY"
    COOK_DAY_MATCH = "COOK_DAY_MATCH"
    COOK_DAY_MISS = "COOK_DAY_MISS"
    BATCH_FRIENDLY = "BATCH_FRIENDLY"
    LEFTOVER_REUSE = "LEFTOVER_REUSE"
    INGREDIENT_REUSE = "INGREDIENT_REUSE"
    PROTEIN_DIVERSITY = "PROTEIN_DIVERSITY"
    RECIPE_DIVERSITY = "RECIPE_DIVERSITY"
    AVOIDED_SIMILAR_MEAL = "AVOIDED_SIMILAR_MEAL"
    GOOD_PAIR = "GOOD_PAIR"
    SHARES_INGREDIENTS = "SHARES_INGREDIENTS"
    STRATEGY_ALIGNMENT = "STRATEGY_ALIGNMENT"
    PREFERRED_PROTEIN_WEEKLY = "PREFERRED_PROTEIN_WEEKLY"
    QUICK_DISTRIBUTION = "QUICK_DISTRIBUTION"


class PlannerViolationCode(StrEnum):
    SLOT_UNFILLED = "SLOT_UNFILLED"
    RECIPE_MISSING = "RECIPE_MISSING"
    MEAL_TYPE_INVALID = "MEAL_TYPE_INVALID"
    EXCLUDED_INGREDIENT = "EXCLUDED_INGREDIENT"
    EXCLUDED_PROTEIN = "EXCLUDED_PROTEIN"
    TIME_LIMIT = "TIME_LIMIT"
    BUDGET_CLASS = "BUDGET_CLASS"
    AVOIDED_RECIPE = "AVOIDED_RECIPE"
    AVOID_CONSECUTIVE_DAYS = "AVOID_CONSECUTIVE_DAYS"
    ORPHAN_LEFTOVER = "ORPHAN_LEFTOVER"
    LEFTOVER_BEFORE_SOURCE = "LEFTOVER_BEFORE_SOURCE"
    LEFTOVER_RECIPE_MISMATCH = "LEFTOVER_RECIPE_MISMATCH"
    LEFTOVER_DISABLED = "LEFTOVER_DISABLED"
    LEFTOVER_OVERCONSUMED = "LEFTOVER_OVERCONSUMED"
    RECIPE_REPEAT = "RECIPE_REPEAT"
    QUALITY_BELOW_MINIMUM = "QUALITY_BELOW_MINIMUM"
    COOKING_INSTANCE_INCONSISTENT = "COOKING_INSTANCE_INCONSISTENT"


PLANNER_REASON_TEXT_RU: dict[str, str] = {
    PlannerReasonCode.SELECTOR_QUALITY: "Хороший локальный score Selector",
    PlannerReasonCode.COOK_DAY_MATCH: "Готовка в день из cook_days",
    PlannerReasonCode.COOK_DAY_MISS: "Готовка вне cook_days (иначе слот не заполнить)",
    PlannerReasonCode.BATCH_FRIENDLY: "Удобно готовить с запасом",
    PlannerReasonCode.LEFTOVER_REUSE: "Использованы остатки предыдущей готовки",
    PlannerReasonCode.INGREDIENT_REUSE: "Повторное использование ингредиентов недели",
    PlannerReasonCode.PROTEIN_DIVERSITY: "Разнообразие источников белка",
    PlannerReasonCode.RECIPE_DIVERSITY: "Разнообразие рецептов недели",
    PlannerReasonCode.AVOIDED_SIMILAR_MEAL: "Избежали похожего блюда подряд",
    PlannerReasonCode.GOOD_PAIR: "Хорошая пара по relations",
    PlannerReasonCode.SHARES_INGREDIENTS: "Общие ингредиенты с другими блюдами",
    PlannerReasonCode.STRATEGY_ALIGNMENT: "Соответствует WeeklyStrategy",
    PlannerReasonCode.PREFERRED_PROTEIN_WEEKLY: "Предпочтительный белок на уровне недели",
    PlannerReasonCode.QUICK_DISTRIBUTION: "Быстрые блюда распределены по неделе",
}


def planner_reason_text_ru(code: str) -> str:
    return PLANNER_REASON_TEXT_RU.get(code, code)
