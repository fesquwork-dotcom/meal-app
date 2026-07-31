"""Deterministic strategy explanation without LLM."""

from __future__ import annotations

import logging
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from strategy.models import WeeklyStrategy
from strategy.reason_codes import infer_reason_codes

logger = logging.getLogger(__name__)

EXPLANATION_VERSION = 1
MAX_HEADLINE_LENGTH = 120
MAX_SUMMARY_LENGTH = 400
MAX_REASONS = 20
MAX_TITLE_LENGTH = 80
MAX_DESCRIPTION_LENGTH = 300

PROTEIN_LABELS: dict[str, str] = {
    "chicken": "курица",
    "beef": "говядина",
    "pork": "свинина",
    "fish": "рыба",
    "seafood": "морепродукты",
    "eggs": "яйца и молочные",
    "veggie": "овощи и бобовые",
}

MEAL_TYPE_LABELS: dict[str, str] = {
    "breakfast": "завтрак",
    "lunch": "обед",
    "dinner": "ужин",
    "snack": "перекус",
}


class StrategyReason(BaseModel):
    model_config = ConfigDict(extra="ignore")

    code: str
    title: str
    description: str
    category: str
    priority: int
    related_days: list[int] = Field(default_factory=list)


class StrategyExplanation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    version: int = EXPLANATION_VERSION
    source: Literal["recorded", "inferred"] = "inferred"
    headline: str
    summary: str
    reasons: list[StrategyReason]


REASON_PRIORITY: dict[str, int] = {
    "GOAL_BUDGET": 1,
    "GOAL_WEIGHT_LOSS": 1,
    "GOAL_MUSCLE": 1,
    "GOAL_HOME": 1,
    "GOAL_HEALTHY": 1,
    "GOAL_RESTAURANT": 1,
    "COOK_DAYS_REDUCE_DAILY_WORK": 2,
    "COOK_DAYS_FAST_MODE": 2,
    "COOK_DAYS_DAILY_VARIETY": 2,
    "LEFTOVERS_REDUCE_COOKING": 3,
    "LEFTOVERS_SUPPORT_BUDGET": 3,
    "BUDGET_LIMITED_VARIETY": 4,
    "COOKING_TIME_LIMIT_FAST": 5,
    "COOKING_TIME_LIMIT_MEDIUM": 5,
    "COOKING_TIME_LIMIT_SLOW": 5,
    "REPEAT_BREAKFASTS_SAVE_TIME": 6,
    "REPEAT_LUNCHES_SUPPORT_BATCH": 6,
    "REPEAT_DINNERS_SUPPORT_BUDGET": 6,
    "SHOPPING_DAYS_SINGLE_TRIP": 7,
    "SHOPPING_DAYS_SPLIT_FRESH_PRODUCTS": 7,
    "PROTEIN_ROTATION_FOR_VARIETY": 8,
    "MEAL_TYPES_CUSTOM": 9,
    "EXCLUSIONS_APPLIED": 10,
    "PROFILE_ALLERGY_CONSTRAINTS_APPLIED": 10,
    "PROFILE_INTOLERANCE_CONSTRAINTS_APPLIED": 10,
    "PROFILE_LEGACY_CONSTRAINTS_APPLIED": 10,
    "PROFILE_PREFERENCE_EXCLUSIONS_APPLIED": 11,
    "MEMORY_AVOID_INGREDIENT_APPLIED": 10,
    "MEMORY_SIGNAL_REDUNDANT_WITH_PROFILE_CONSTRAINT": 12,
    "MEMORY_FASTER_MEALS_APPLIED": 5,
    "PROFILE_FASTER_MEALS_PREFERENCE_APPLIED": 5,
    "PROFILE_FASTER_MEALS_DISABLED": 12,
    "MEMORY_FASTER_MEALS_REDUNDANT_WITH_PROFILE": 12,
    "BEHAVIOR_AVAILABILITY_FRICTION_APPLIED": 11,
    "PROFILE_FAMILIAR_MEALS_PREFERENCE_APPLIED": 11,
    "PROFILE_FAMILIAR_MEALS_PREFERENCE_DISABLED": 12,
}


def _truncate(text: str, limit: int) -> str:
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[: limit - 1].rstrip() + "…"


def _format_days(days: list[int]) -> str:
    return ", ".join(str(day) for day in sorted(days))


def _format_budget(amount: float) -> str:
    rounded = int(amount) if float(amount).is_integer() else round(amount, 2)
    return f"{rounded:,}".replace(",", " ")


def _format_proteins(proteins: list[str]) -> str:
    labels = [PROTEIN_LABELS.get(item, item) for item in proteins if item != "any"]
    if len(labels) <= 1:
        return labels[0] if labels else ""
    if len(labels) == 2:
        return f"{labels[0]} и {labels[1]}"
    return ", ".join(labels[:-1]) + f" и {labels[-1]}"


def _format_meal_types(meal_types: list[str]) -> str:
    return ", ".join(MEAL_TYPE_LABELS.get(item, item) for item in meal_types)


def _build_reason(code: str, strategy: WeeklyStrategy) -> StrategyReason | None:
    cook_days = sorted(strategy.cook_days)
    shopping_days = sorted(strategy.shopping_days)
    all_days = list(range(1, strategy.days + 1))
    priority = REASON_PRIORITY.get(code, 99)

    if code == "COOK_DAYS_REDUCE_DAILY_WORK":
        return StrategyReason(
            code=code,
            title="Меньше дней готовки",
            description=(
                f"Готовка распределена на дни {_format_days(cook_days)}. "
                "В остальные дни план использует блюда без новой полноценной готовки."
            ),
            category="cooking",
            priority=priority,
            related_days=cook_days,
        )

    if code == "COOK_DAYS_DAILY_VARIETY":
        return StrategyReason(
            code=code,
            title="Ежедневная готовка",
            description=(
                "План допускает готовку каждый день, чтобы сохранить максимальное разнообразие блюд."
            ),
            category="cooking",
            priority=priority,
            related_days=all_days,
        )

    if code == "COOK_DAYS_FAST_MODE":
        return StrategyReason(
            code=code,
            title="Быстрые блюда",
            description=(
                "План рассчитан на короткие сессии готовки и простые блюда в каждый день периода."
            ),
            category="cooking",
            priority=priority,
            related_days=all_days,
        )

    if code == "LEFTOVERS_REDUCE_COOKING":
        return StrategyReason(
            code=code,
            title="Переиспользование заготовок",
            description=(
                "Часть блюд и заготовок используется повторно в следующих приёмах пищи. "
                "Это сокращает число приготовлений и помогает не покупать лишние продукты."
            ),
            category="leftovers",
            priority=priority,
        )

    if code == "LEFTOVERS_SUPPORT_BUDGET":
        return StrategyReason(
            code=code,
            title="Остатки помогают бюджету",
            description=(
                "Повторное использование приготовленных блюд снижает расход продуктов и стоимость корзины."
            ),
            category="budget",
            priority=priority,
        )

    if code == "REPEAT_BREAKFASTS_SAVE_TIME":
        return StrategyReason(
            code=code,
            title="Повторяющиеся завтраки",
            description=(
                "Некоторые завтраки повторяются, чтобы утром не тратить время на новый выбор и приготовление."
            ),
            category="repeats",
            priority=priority,
        )

    if code == "REPEAT_LUNCHES_SUPPORT_BATCH":
        return StrategyReason(
            code=code,
            title="Повторяющиеся обеды",
            description=(
                "Обеды могут повторяться, чтобы использовать batch-заготовки и уменьшить количество готовки."
            ),
            category="repeats",
            priority=priority,
        )

    if code == "REPEAT_DINNERS_SUPPORT_BUDGET":
        return StrategyReason(
            code=code,
            title="Повторяющиеся ужины",
            description=(
                "Часть ужинов повторяется для снижения стоимости корзины и пищевых отходов."
            ),
            category="repeats",
            priority=priority,
        )

    if code == "SHOPPING_DAYS_SINGLE_TRIP":
        return StrategyReason(
            code=code,
            title="Одна основная закупка",
            description="Основная закупка запланирована один раз в начале периода.",
            category="shopping",
            priority=priority,
            related_days=shopping_days,
        )

    if code == "SHOPPING_DAYS_SPLIT_FRESH_PRODUCTS":
        return StrategyReason(
            code=code,
            title="Закупка в два этапа",
            description=(
                f"Закупка разделена на дни {_format_days(shopping_days)}, "
                "чтобы свежие продукты второй половины периода не пришлось покупать слишком заранее."
            ),
            category="shopping",
            priority=priority,
            related_days=shopping_days,
        )

    if code == "BUDGET_LIMITED_VARIETY":
        return StrategyReason(
            code=code,
            title="Ориентир по бюджету",
            description=(
                f"Меню построено в пределах ориентировочного бюджета {_format_budget(strategy.budget)} ₽. "
                "Целевой ориентир использования — 90–100% бюджета за счёт качества продуктов, "
                "а не лишних блюд. Расчётная стоимость покупки может немного отличаться от стоимости рецептов."
            ),
            category="budget",
            priority=priority,
        )

    if code == "COOKING_TIME_LIMIT_FAST":
        return StrategyReason(
            code=code,
            title="Быстрая готовка",
            description=(
                f"Активное приготовление одного блюда ограничено примерно {strategy.cooking_time_limit} минутами."
            ),
            category="time",
            priority=priority,
        )

    if code == "COOKING_TIME_LIMIT_MEDIUM":
        return StrategyReason(
            code=code,
            title="Средняя длительность готовки",
            description=(
                "План рассчитан на блюда со средней продолжительностью активной готовки "
                f"— до {strategy.cooking_time_limit} минут."
            ),
            category="time",
            priority=priority,
        )

    if code == "COOKING_TIME_LIMIT_SLOW":
        return StrategyReason(
            code=code,
            title="Длительная готовка",
            description=(
                f"План допускает активную готовку до {strategy.cooking_time_limit} минут на блюдо."
            ),
            category="time",
            priority=priority,
        )

    if code == "PROTEIN_ROTATION_FOR_VARIETY":
        protein_text = _format_proteins(strategy.preferred_proteins)
        if not protein_text:
            return None
        return StrategyReason(
            code=code,
            title="Чередование белков",
            description=(
                f"В течение периода чередуются {protein_text}, "
                "чтобы план не состоял из одного основного продукта."
            ),
            category="proteins",
            priority=priority,
        )

    if code == "MEAL_TYPES_CUSTOM":
        return StrategyReason(
            code=code,
            title="Структура приёмов пищи",
            description=f"План включает {_format_meal_types(strategy.meal_types)} на каждый день.",
            category="meals",
            priority=priority,
        )

    if code == "EXCLUSIONS_APPLIED":
        return StrategyReason(
            code=code,
            title="Исключения учтены",
            description="Исключённые продукты учтены во всех рецептах и корзине.",
            category="exclusions",
            priority=priority,
        )

    if code in {
        "PROFILE_ALLERGY_CONSTRAINTS_APPLIED",
        "PROFILE_INTOLERANCE_CONSTRAINTS_APPLIED",
        "PROFILE_LEGACY_CONSTRAINTS_APPLIED",
    }:
        # Safety template: no allergen listing, no medical wording.
        return StrategyReason(
            code=code,
            title="Ограничения по продуктам",
            description="Указанные ограничения по продуктам строго исключены из рецептов и корзины.",
            category="exclusions",
            priority=priority,
        )

    if code == "PROFILE_PREFERENCE_EXCLUSIONS_APPLIED":
        return StrategyReason(
            code=code,
            title="Вкусовые исключения",
            description="Ваши вкусовые исключения учтены при подборе блюд.",
            category="exclusions",
            priority=priority,
        )

    if code == "MEMORY_SIGNAL_REDUNDANT_WITH_PROFILE_CONSTRAINT":
        return StrategyReason(
            code=code,
            title="Предпочтение уже учтено",
            description="Продукт уже исключён настройками профиля.",
            category="memory",
            priority=priority,
        )

    if code == "MEMORY_AVOID_INGREDIENT_APPLIED":
        return StrategyReason(
            code=code,
            title="Предпочтения по продуктам",
            description="Подтверждённые предпочтения по продуктам учтены в меню.",
            category="memory",
            priority=priority,
        )

    if code == "MEMORY_FASTER_MEALS_APPLIED":
        return StrategyReason(
            code=code,
            title="Более быстрые блюда",
            description=(
                "При прочих равных приложение выберет более быстрые блюда "
                "в пределах допустимого времени готовки."
            ),
            category="memory",
            priority=priority,
        )

    if code == "PROFILE_FASTER_MEALS_PREFERENCE_APPLIED":
        return StrategyReason(
            code=code,
            title="Предпочтение быстрых блюд",
            description=(
                "В профиле включено предпочтение более быстрых блюд. "
                "При прочих равных будут выбраны варианты с меньшим активным временем."
            ),
            category="profile",
            priority=priority,
        )

    if code == "PROFILE_FASTER_MEALS_DISABLED":
        return StrategyReason(
            code=code,
            title="Быстрые блюда отключены",
            description="В профиле отключено предпочтение более быстрых блюд.",
            category="profile",
            priority=priority,
        )

    if code == "MEMORY_FASTER_MEALS_REDUNDANT_WITH_PROFILE":
        return StrategyReason(
            code=code,
            title="Предпочтение уже в профиле",
            description="Предпочтение быстрых блюд уже задано в настройках профиля.",
            category="memory",
            priority=priority,
        )

    if code == "BEHAVIOR_AVAILABILITY_FRICTION_APPLIED":
        return StrategyReason(
            code=code,
            title="Наблюдения о доступности",
            description=(
                "Подтверждённые наблюдения о доступности продуктов учтены при подборе меню."
            ),
            category="behavior",
            priority=priority,
        )

    if code == "PROFILE_FAMILIAR_MEALS_PREFERENCE_APPLIED":
        return StrategyReason(
            code=code,
            title="Знакомые блюда",
            description=(
                "В профиле включено предпочтение более знакомых и предсказуемых блюд."
            ),
            category="profile",
            priority=priority,
        )

    if code.startswith("BEHAVIOR_"):
        return None

    goal_titles: dict[str, tuple[str, str]] = {
        "GOAL_BUDGET": (
            "Экономный подход",
            "Стратегия отдаёт приоритет стоимости, повторному использованию продуктов и сокращению лишних покупок.",
        ),
        "GOAL_WEIGHT_LOSS": (
            "Цель — снижение веса",
            "Стратегия учитывает цель снижения веса при подборе структуры меню.",
        ),
        "GOAL_MUSCLE": (
            "Цель — набор массы",
            "Стратегия учитывает повышенное внимание к белковым блюдам и регулярности питания.",
        ),
        "GOAL_HOME": (
            "Домашняя еда",
            "Стратегия ориентирована на привычные домашние блюда и практичное планирование.",
        ),
        "GOAL_HEALTHY": (
            "Правильное питание",
            "Стратегия учитывает сбалансированную структуру меню и переиспользование заготовок.",
        ),
        "GOAL_RESTAURANT": (
            "Ресторан дома",
            "Стратегия допускает более разнообразные блюда и кулинарные приёмы.",
        ),
    }

    if code in goal_titles:
        title, description = goal_titles[code]
        return StrategyReason(
            code=code,
            title=title,
            description=description,
            category="goal",
            priority=priority,
        )

    return None


def _build_headline(strategy: WeeklyStrategy, reason_codes: list[str]) -> str:
    cook_count = len(strategy.cook_days)
    all_days = list(range(1, strategy.days + 1))

    if "GOAL_BUDGET" in reason_codes and (
        strategy.repeat_breakfasts or strategy.repeat_lunches or strategy.repeat_dinners
    ):
        return _truncate("Экономный план с повторными приёмами", MAX_HEADLINE_LENGTH)

    if strategy.cook_days != all_days and cook_count >= 2:
        cook_word = {2: "два", 3: "три", 4: "четыре"}.get(cook_count, str(cook_count))
        return _truncate(f"Неделя с готовкой {cook_word} раза", MAX_HEADLINE_LENGTH)

    if "COOKING_TIME_LIMIT_FAST" in reason_codes:
        return _truncate("Быстрое меню на неделю", MAX_HEADLINE_LENGTH)

    if strategy.goal == "healthy":
        return _truncate("Сбалансированный недельный план", MAX_HEADLINE_LENGTH)

    if strategy.goal == "home":
        return _truncate("Домашний план на неделю", MAX_HEADLINE_LENGTH)

    return _truncate("Персональный план питания", MAX_HEADLINE_LENGTH)


def _build_summary(strategy: WeeklyStrategy, reasons: list[StrategyReason]) -> str:
    parts: list[str] = []
    cook_days = sorted(strategy.cook_days)
    all_days = list(range(1, strategy.days + 1))

    if strategy.cook_days != all_days:
        parts.append(
            f"Основные блюда готовятся в дни {_format_days(cook_days)}. "
            "В остальные дни используются готовые блюда и заготовки."
        )
    else:
        parts.append("План рассчитан на готовку в каждый день периода.")

    if strategy.leftovers_enabled:
        parts.append(
            "Переиспользование заготовок помогает сократить время на кухне и удержать план в рамках бюджета."
        )

    if strategy.goal == "budget":
        parts.append(
            f"Ориентировочный бюджет — {_format_budget(strategy.budget)} ₽ на весь период."
        )

    if not parts:
        top = reasons[:2]
        parts.extend(reason.description for reason in top)

    summary = " ".join(parts)
    return _truncate(summary, MAX_SUMMARY_LENGTH)


def build_strategy_explanation(
    strategy: WeeklyStrategy,
    *,
    reason_codes: list[str] | None = None,
    source: Literal["recorded", "inferred"] = "inferred",
) -> StrategyExplanation:
    """Builds a deterministic user-facing explanation from strategy data."""
    codes = sorted(set(reason_codes or infer_reason_codes(strategy)))
    reasons: list[StrategyReason] = []

    for code in codes:
        reason = _build_reason(code, strategy)
        if reason is not None:
            reasons.append(reason)

    reasons.sort(key=lambda item: (item.priority, item.code))
    reasons = reasons[:MAX_REASONS]

    unknown = [code for code in codes if code not in {reason.code for reason in reasons}]
    if unknown:
        logger.info(
            "strategy_explanation unknown_codes=%s count=%s",
            unknown[:5],
            len(unknown),
        )

    headline = _build_headline(strategy, codes)
    summary = _build_summary(strategy, reasons)

    logger.info(
        "strategy_explanation source=%s version=%s reason_count=%s codes=%s",
        source,
        EXPLANATION_VERSION,
        len(reasons),
        len(codes),
    )

    return StrategyExplanation(
        version=EXPLANATION_VERSION,
        source=source,
        headline=headline,
        summary=summary,
        reasons=reasons,
    )
