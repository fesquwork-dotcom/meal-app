"""Filter / soft reason codes and Russian labels."""

from __future__ import annotations

from enum import StrEnum


class HardFilterCode(StrEnum):
    INACTIVE_RECIPE = "INACTIVE_RECIPE"
    MEAL_TYPE_MISMATCH = "MEAL_TYPE_MISMATCH"
    EXCLUDED_INGREDIENT = "EXCLUDED_INGREDIENT"
    EXCLUDED_PROTEIN_SOURCE = "EXCLUDED_PROTEIN_SOURCE"
    REQUIRED_TAG_MISSING = "REQUIRED_TAG_MISSING"
    EXCLUDED_TAG_PRESENT = "EXCLUDED_TAG_PRESENT"
    TIME_LIMIT_EXCEEDED = "TIME_LIMIT_EXCEEDED"
    BUDGET_CLASS_NOT_ALLOWED = "BUDGET_CLASS_NOT_ALLOWED"
    REQUIRED_EQUIPMENT_UNAVAILABLE = "REQUIRED_EQUIPMENT_UNAVAILABLE"
    AVOIDED_RECIPE = "AVOIDED_RECIPE"


class SoftReasonCode(StrEnum):
    GOAL_MATCH = "GOAL_MATCH"
    BUDGET_FRIENDLY = "BUDGET_FRIENDLY"
    QUICK_PREPARATION = "QUICK_PREPARATION"
    PREFERRED_INGREDIENT_MATCH = "PREFERRED_INGREDIENT_MATCH"
    PREFERRED_PROTEIN_SOURCE = "PREFERRED_PROTEIN_SOURCE"
    PREFERRED_TAG_MATCH = "PREFERRED_TAG_MATCH"
    ROLE_MATCH = "ROLE_MATCH"
    BATCH_FRIENDLY = "BATCH_FRIENDLY"
    LEFTOVER_FRIENDLY = "LEFTOVER_FRIENDLY"
    FAMILY_FRIENDLY = "FAMILY_FRIENDLY"
    REPEATED_INGREDIENT_PENALTY = "REPEATED_INGREDIENT_PENALTY"
    LOW_GOAL_SCORE = "LOW_GOAL_SCORE"
    LOW_ROLE_SCORE = "LOW_ROLE_SCORE"


REASON_TEXT_RU: dict[str, str] = {
    SoftReasonCode.GOAL_MATCH: "Хорошо соответствует выбранной цели питания",
    SoftReasonCode.BUDGET_FRIENDLY: "Подходит по бюджетному классу",
    SoftReasonCode.QUICK_PREPARATION: "Укладывается в предпочтительное время приготовления",
    SoftReasonCode.PREFERRED_INGREDIENT_MATCH: "Содержит предпочтительные ингредиенты",
    SoftReasonCode.PREFERRED_PROTEIN_SOURCE: "Предпочтительный источник белка",
    SoftReasonCode.PREFERRED_TAG_MATCH: "Совпадает с предпочтительными тегами",
    SoftReasonCode.ROLE_MATCH: "Подходит под желаемую роль в плане",
    SoftReasonCode.BATCH_FRIENDLY: "Удобно готовить с запасом",
    SoftReasonCode.LEFTOVER_FRIENDLY: "Хорошо хранится как остатки",
    SoftReasonCode.FAMILY_FRIENDLY: "Подходит для семейного приёма пищи",
    SoftReasonCode.REPEATED_INGREDIENT_PENALTY: "Повторяет недавно использованные ингредиенты",
    SoftReasonCode.LOW_GOAL_SCORE: "Слабее соответствует выбранной цели",
    SoftReasonCode.LOW_ROLE_SCORE: "Слабо подходит под желаемую роль",
    HardFilterCode.INACTIVE_RECIPE: "Рецепт не активен",
    HardFilterCode.MEAL_TYPE_MISMATCH: "Не подходит для этого приёма пищи",
    HardFilterCode.EXCLUDED_INGREDIENT: "Содержит исключённый ингредиент",
    HardFilterCode.EXCLUDED_PROTEIN_SOURCE: "Исключённый источник белка",
    HardFilterCode.REQUIRED_TAG_MISSING: "Нет обязательного тега",
    HardFilterCode.EXCLUDED_TAG_PRESENT: "Содержит исключённый тег",
    HardFilterCode.TIME_LIMIT_EXCEEDED: "Превышает лимит времени готовки",
    HardFilterCode.BUDGET_CLASS_NOT_ALLOWED: "Бюджетный класс не разрешён",
    HardFilterCode.REQUIRED_EQUIPMENT_UNAVAILABLE: "Нужна недоступная техника",
    HardFilterCode.AVOIDED_RECIPE: "Рецепт в списке избегаемых",
}


def reason_text_ru(code: str) -> str:
    return REASON_TEXT_RU.get(code, code)
