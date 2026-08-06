"""Safe, deterministic user-facing explanations derived from DecisionTrace."""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from decision.trace_diff import compare_decision_traces
from decision.trace_models import DecisionTrace, DecisionTraceEntry
from decision.versions import DECISION_EXPLANATION_VERSION
from strategy.explanation import StrategyExplanation
from strategy.models import WeeklyStrategy

logger = logging.getLogger(__name__)

MAX_EXPLANATIONS = 8
MAX_PREVIEW_EXPLANATIONS = 3
MAX_SUPPORTING_POINTS = 4

EXPLAINABLE_KEYS = frozenset(
    {
        "budget.weekly",
        "cooking.time_limit",
        "cooking.prefer_faster",
        "cooking.cook_days",
        "cooking.batch_allowed",
        "shopping.days",
        "meal.leftovers_enabled",
        "meal.repeat_breakfasts",
        "meal.repeat_lunches",
        "meal.repeat_dinners",
        "protein.preferred",
        "protein.excluded",
        "exclusions.count",
        "behavior.availability_avoid_products",
        "planning.prefer_familiar_meals",
    }
)

EXPLANATION_ORDER = (
    "cooking.cook_days",
    "cooking.time_limit",
    "cooking.prefer_faster",
    "shopping.days",
    "budget.weekly",
    "cooking.batch_allowed",
    "meal.leftovers_enabled",
    "meal.repeat_breakfasts",
    "meal.repeat_lunches",
    "meal.repeat_dinners",
    "planning.prefer_familiar_meals",
    "behavior.availability_avoid_products",
    "protein.preferred",
    "protein.excluded",
    "exclusions.count",
)

CONFIDENCE_LABELS = {
    "explicit": "Задано вами",
    "deterministic": "Рассчитано по правилам плана",
    "inferred": "Учтено по подтверждённым предпочтениям",
    "fallback": "Использовано стандартное значение",
}

SOURCE_LABELS = {
    "profile": "Настройки профиля",
    "learned_preference": "Принятое адаптивное предпочтение",
    "memory": "Подтверждённые предпочтения",
    "behavior": "Подтверждённые наблюдения",
    "default": "Стандартные настройки",
    "rule": "Правила планирования",
    "runtime": "Параметры планирования",
}

PROTEIN_LABELS = {
    "chicken": "курица",
    "beef": "говядина",
    "pork": "свинина",
    "fish": "рыба",
    "seafood": "морепродукты",
    "eggs": "яйца и молочные продукты",
    "veggie": "овощи и бобовые",
}

KNOWN_RULE_CODES = frozenset(
    {
        "BUDGET_WEEKLY_FROM_PROFILE",
        "BUDGET_WEEKLY_DEFAULT",
        "BUDGET_DAILY_DERIVED",
        "COOKING_TIME_LIMIT_FROM_COOKTIME",
        "MEMORY_FASTER_TIME_DOWNGRADE",
        "PROFILE_FASTER_PREFERENCE",
        "MEMORY_FASTER_PREFERENCE",
        "LEARNED_FASTER_PREFERENCE",
        "PREFER_FASTER_NOT_ENABLED",
        "COOK_DAYS_DAILY_FAST",
        "COOK_DAYS_BATCH_GOAL",
        "COOK_DAYS_DAILY_VARIETY",
        "BATCH_ALLOWED_DERIVED",
        "PROTEIN_PREFERRED_FROM_PROFILE",
        "PROTEIN_PREFERRED_DEFAULT_ANY",
        "MEMORY_PROTEIN_CONFLICT_REMOVAL",
        "SHOPPING_SPLIT_FRESH",
        "SHOPPING_SINGLE_TRIP",
        "LEFTOVERS_GOAL_RULE",
        "REPEAT_BREAKFASTS_GOAL_RULE",
        "REPEAT_LUNCHES_GOAL_RULE",
        "REPEAT_DINNERS_GOAL_RULE",
        "MEMORY_AVOID_EXCLUSION",
        "BEHAVIOR_AVAILABILITY_FRICTION",
        "PROFILE_FAMILIAR_PREFERENCE",
        "LEARNED_FAMILIAR_PREFERENCE",
        "PLANNING_FAMILIAR_DEFAULT",
    }
)


class DecisionExplanation(BaseModel):
    """Public explanation model. Technical trace details are intentionally absent."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    version: int = DECISION_EXPLANATION_VERSION
    decision_key: str = Field(max_length=80)
    title: str = Field(max_length=80)
    outcome: str = Field(max_length=160)
    explanation: str = Field(max_length=400)
    source_label: str | None = Field(default=None, max_length=80)
    supporting_points: list[str] = Field(default_factory=list, max_length=MAX_SUPPORTING_POINTS)
    alternative_note: str | None = Field(default=None, max_length=300)
    confidence_label: str | None = Field(default=None, max_length=80)


class DecisionExplanationCollection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    version: int = DECISION_EXPLANATION_VERSION
    headline: str = Field(max_length=120)
    summary: str = Field(max_length=400)
    explanations: list[DecisionExplanation] = Field(
        default_factory=list, max_length=MAX_EXPLANATIONS
    )
    source: Literal["trace", "legacy"]


class DecisionExplanationChange(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    decision_key: str = Field(max_length=80)
    title: str = Field(max_length=80)
    before: str = Field(max_length=160)
    after: str = Field(max_length=160)
    explanation: str = Field(max_length=300)
    change_type: Literal["value_changed", "source_changed", "rule_changed"]


def _format_number(value: float) -> str:
    rounded = int(value) if float(value).is_integer() else round(value, 2)
    return f"{rounded:,}".replace(",", " ")


def _format_days(days: list[int]) -> str:
    values = [str(day) for day in sorted(days)]
    if len(values) <= 1:
        return values[0] if values else ""
    return ", ".join(values[:-1]) + f" и {values[-1]}"


def _winner_source(entry: DecisionTraceEntry) -> str | None:
    if entry.confidence == "fallback":
        return SOURCE_LABELS["default"]
    return SOURCE_LABELS.get(entry.priority_winner or "")


def _has_rule(entry: DecisionTraceEntry, code: str, *, rejected: bool = False) -> bool:
    rules = entry.rejected_rules if rejected else entry.applied_rules
    return any(rule.rule_code == code for rule in rules)


def _base(
    entry: DecisionTraceEntry,
    *,
    title: str,
    outcome: str,
    explanation: str,
    supporting_points: list[str] | None = None,
    alternative_note: str | None = None,
) -> DecisionExplanation:
    return DecisionExplanation(
        decision_key=entry.decision_key,
        title=title,
        outcome=outcome,
        explanation=explanation,
        source_label=_winner_source(entry),
        supporting_points=(supporting_points or [])[:MAX_SUPPORTING_POINTS],
        alternative_note=alternative_note,
        confidence_label=CONFIDENCE_LABELS.get(entry.confidence),
    )


def _explain_entry(
    entry: DecisionTraceEntry,
    strategy: WeeklyStrategy,
) -> DecisionExplanation | None:
    key = entry.decision_key

    if key == "budget.weekly":
        fallback = entry.confidence == "fallback"
        return _base(
            entry,
            title="Недельный бюджет",
            outcome=f"Около {_format_number(strategy.budget)} ₽",
            explanation=(
                "Бюджет не был задан явно, поэтому использовано стандартное значение."
                if fallback
                else "Ориентир бюджета взят из настроек профиля."
            ),
            supporting_points=["Фактическая стоимость корзины может отличаться."],
        )

    if key == "cooking.time_limit":
        source_text = {
            "profile": "Лимит взят из настроек профиля.",
            "memory": "Учтено подтверждённое предпочтение более быстрых блюд.",
            "default": "Использовано стандартное ограничение времени.",
        }.get(
            "default" if entry.confidence == "fallback" else entry.priority_winner,
            "Лимит рассчитан по правилам плана.",
        )
        return _base(
            entry,
            title="Время готовки",
            outcome=f"До {strategy.cooking_time_limit} минут",
            explanation=(
                f"Активное приготовление каждого блюда ограничено "
                f"{strategy.cooking_time_limit} минутами. {source_text}"
            ),
        )

    if key == "cooking.prefer_faster":
        if strategy.prefer_faster_meals:
            explanation = (
                "При прочих равных план отдаёт предпочтение блюдам с меньшим активным временем."
            )
            if entry.priority_winner == "memory":
                explanation += " Учтено подтверждённое предпочтение из прошлых замен."
            elif entry.priority_winner == "learned_preference":
                explanation += (
                    " Учтено адаптивное предпочтение более быстрых блюд, "
                    "которое вы ранее разрешили использовать."
                )
            return _base(
                entry,
                title="Предпочтение быстрых блюд",
                outcome="Включено",
                explanation=explanation,
            )
        if entry.priority_winner != "profile":
            return None
        priority_note = None
        if any(
            rule.result == "skipped"
            and rule.rule_code
            in {"MEMORY_FASTER_PREFERENCE", "LEARNED_FASTER_PREFERENCE"}
            for rule in entry.rejected_rules
        ):
            priority_note = (
                "Настройка профиля имеет приоритет, поэтому адаптивное "
                "предпочтение не применяется."
            )
        return _base(
            entry,
            title="Предпочтение быстрых блюд",
            outcome="Выключено",
            explanation="В профиле отключено предпочтение более быстрых блюд.",
            alternative_note=priority_note,
        )

    if key == "cooking.cook_days":
        days = list(strategy.cook_days)
        daily = days == list(range(1, strategy.days + 1))
        if daily:
            if not strategy.leftovers_enabled:
                return _base(
                    entry,
                    title="Дни готовки",
                    outcome="Каждый день",
                    explanation=(
                        "Поскольку блюда на следующий день не используются, "
                        "приготовление распределено по каждому дню."
                    ),
                )
            text = (
                "План допускает готовку каждый день, потому что выбран короткий "
                "лимит активного времени."
                if _has_rule(entry, "COOK_DAYS_DAILY_FAST")
                else "План допускает готовку каждый день для большего разнообразия."
            )
            return _base(
                entry,
                title="Дни готовки",
                outcome="Каждый день",
                explanation=text,
            )
        alternative = None
        if _has_rule(entry, "COOK_DAYS_DAILY_FAST", rejected=True):
            alternative = (
                "Ежедневная готовка не выбрана, потому что заданный лимит времени "
                "не относится к быстрому режиму."
            )
        # Sparse cook days imply leftover/batch coverage in current semantics.
        leftover_note = (
            "Основную готовку можно распределить по этим дням, а в остальные "
            "использовать заготовки или блюда без новой полноценной готовки."
            if strategy.leftovers_enabled
            else (
                "Основную готовку можно распределить по этим дням; "
                "в остальные дни нужна готовка или блюда без новой полноценной готовки."
            )
        )
        return _base(
            entry,
            title="Дни готовки",
            outcome=f"Дни {_format_days(days)}",
            explanation=leftover_note,
            alternative_note=alternative,
        )

    if key == "cooking.batch_allowed":
        if entry.outcome.value is not True:
            return None
        return _base(
            entry,
            title="Приготовление партиями",
            outcome="Можно использовать",
            explanation=(
                "План допускает приготовление партиями, чтобы сократить число "
                "полноценных готовок в течение недели."
            ),
        )

    if key == "shopping.days":
        days = list(strategy.shopping_days)
        if len(days) <= 1:
            return _base(
                entry,
                title="Закупки",
                outcome="Одна основная закупка",
                explanation="Продукты рассчитаны на одну основную закупку.",
            )
        return _base(
            entry,
            title="Закупки",
            outcome=f"Дни {_format_days(days)}",
            explanation=(
                "Закупка разделена на несколько дней, чтобы свежие продукты "
                "не пришлось покупать слишком заранее."
            ),
        )

    if key == "meal.leftovers_enabled":
        if not strategy.leftovers_enabled:
            return None
        return _base(
            entry,
            title="Заготовки и остатки",
            outcome="Используются",
            explanation=(
                "В плане используются заготовки и остатки, чтобы уменьшить "
                "число полноценных готовок."
            ),
        )

    if key.startswith("meal.repeat_"):
        enabled = (
            strategy.repeat_breakfasts
            or strategy.repeat_lunches
            or strategy.repeat_dinners
        )
        if not enabled or key != next(
            candidate
            for candidate, active in (
                ("meal.repeat_breakfasts", strategy.repeat_breakfasts),
                ("meal.repeat_lunches", strategy.repeat_lunches),
                ("meal.repeat_dinners", strategy.repeat_dinners),
            )
            if active
        ):
            return None
        return _base(
            entry,
            title="Повторы приёмов пищи",
            outcome="Некоторые блюда могут повторяться",
            explanation=(
                "Некоторые приёмы пищи повторяются, чтобы сделать неделю "
                "проще и предсказуемее."
            ),
        )

    if key == "planning.prefer_familiar_meals":
        if not strategy.prefer_familiar_meals:
            return None
        return _base(
            entry,
            title="Знакомые блюда",
            outcome="Предпочтение включено",
            explanation=(
                "Учтено адаптивное предпочтение более знакомых блюд, "
                "которое вы ранее разрешили использовать."
                if entry.priority_winner == "learned_preference"
                else (
                    "В профиле включено предпочтение более знакомых и "
                    "предсказуемых блюд."
                )
            ),
        )

    if key == "behavior.availability_avoid_products":
        if not strategy.availability_avoid_products:
            return None
        return _base(
            entry,
            title="Доступность продуктов",
            outcome="Наблюдения учтены",
            explanation=(
                "При выборе продуктов учтены подтверждённые наблюдения "
                "о доступности товаров."
            ),
        )

    if key == "protein.preferred":
        proteins = [
            PROTEIN_LABELS.get(item, item)
            for item in strategy.preferred_proteins
            if item != "any"
        ]
        if not proteins:
            return None
        return _base(
            entry,
            title="Основные источники белка",
            outcome=", ".join(proteins),
            explanation=(
                "Эти варианты будут чередоваться, чтобы план оставался разнообразным."
            ),
        )

    if key in {"protein.excluded", "exclusions.count"}:
        if not strategy.excluded_products:
            return None
        return DecisionExplanation(
            decision_key=entry.decision_key,
            title="Ограничения по продуктам",
            outcome="Учтены",
            explanation="Ограничения по продуктам учтены при построении плана.",
            source_label=None,
            supporting_points=[],
            alternative_note=None,
            confidence_label=None,
        )

    return None


def build_decision_explanations(
    trace: DecisionTrace,
    *,
    strategy: WeeklyStrategy,
    max_explanations: int = MAX_EXPLANATIONS,
) -> DecisionExplanationCollection:
    """Render allowlisted trace entries without exposing technical provenance."""
    entries = {entry.decision_key: entry for entry in trace.entries}
    explanations: list[DecisionExplanation] = []
    unknown_rules = sorted(
        {
            rule.rule_code
            for entry in trace.entries
            if entry.decision_key in EXPLAINABLE_KEYS
            for rule in (*entry.applied_rules, *entry.rejected_rules)
            if rule.rule_code not in KNOWN_RULE_CODES
        }
    )
    if unknown_rules:
        logger.info(
            "decision_explanation_unknown_rule rule_count=%s decision_keys=%s",
            len(unknown_rules),
            sorted(
                {
                    entry.decision_key
                    for entry in trace.entries
                    if any(
                        rule.rule_code in unknown_rules
                        for rule in (*entry.applied_rules, *entry.rejected_rules)
                    )
                }
            ),
        )

    for key in EXPLANATION_ORDER:
        entry = entries.get(key)
        if entry is None or key not in EXPLAINABLE_KEYS:
            continue
        explanation = _explain_entry(entry, strategy)
        if explanation is not None:
            explanations.append(explanation)

    limit = max(0, min(max_explanations, MAX_EXPLANATIONS))
    truncated = len(explanations) > limit
    explanations = explanations[:limit]
    logger.info(
        "decision_explanations_built source=trace explanation_count=%s "
        "decision_keys=%s truncated=%s",
        len(explanations),
        [item.decision_key for item in explanations],
        truncated,
    )
    if truncated:
        logger.info(
            "decision_explanation_truncated explanation_count=%s limit=%s",
            len(explanations),
            limit,
        )
    return DecisionExplanationCollection(
        headline="Почему выбраны именно такие настройки",
        summary=(
            "Объяснения основаны на настройках профиля, подтверждённых "
            "предпочтениях и правилах планирования."
        ),
        explanations=explanations,
        source="trace",
    )


def build_legacy_decision_explanations(
    explanation: StrategyExplanation,
) -> DecisionExplanationCollection:
    """Limited fallback: no priority or rejected-rule claims without a trace."""
    items = [
        DecisionExplanation(
            decision_key=f"legacy.{index}",
            title=reason.title,
            outcome="Учтено в плане",
            explanation=reason.description,
            source_label=None,
            supporting_points=[],
            alternative_note=None,
            confidence_label=None,
        )
        for index, reason in enumerate(explanation.reasons[:MAX_EXPLANATIONS])
    ]
    logger.info(
        "decision_explanations_legacy_fallback explanation_count=%s source=legacy",
        len(items),
    )
    return DecisionExplanationCollection(
        headline=explanation.headline,
        summary=explanation.summary,
        explanations=items,
        source="legacy",
    )


def build_decision_explanation_changes(
    current_trace: DecisionTrace | None,
    next_trace: DecisionTrace | None,
    *,
    current_strategy: WeeklyStrategy,
    next_strategy: WeeklyStrategy,
) -> list[DecisionExplanationChange] | None:
    """Present a privacy-safe subset of DecisionTraceDiff."""
    diff = compare_decision_traces(current_trace, next_trace)
    if not diff.current_trace_available or not diff.next_trace_available:
        return None

    current_entries = {
        entry.decision_key: entry for entry in (current_trace.entries if current_trace else [])
    }
    next_entries = {
        entry.decision_key: entry for entry in (next_trace.entries if next_trace else [])
    }
    changes_by_key = {change.decision_key: change for change in diff.changes}
    presented: list[DecisionExplanationChange] = []

    for key in EXPLANATION_ORDER:
        technical = changes_by_key.get(key)
        current_entry = current_entries.get(key)
        next_entry = next_entries.get(key)
        if (
            technical is None
            or current_entry is None
            or next_entry is None
            or key not in EXPLAINABLE_KEYS
        ):
            continue
        before = _explain_entry(current_entry, current_strategy)
        after = _explain_entry(next_entry, next_strategy)
        if before is None or after is None:
            continue

        if technical.value_changed:
            change_type: Literal["value_changed", "source_changed", "rule_changed"] = (
                "value_changed"
            )
            explanation = "Настройка изменится вместе с параметрами будущего плана."
        elif technical.winner_changed or technical.confidence_changed:
            change_type = "source_changed"
            explanation = "Изменился источник, на котором основана эта настройка."
        else:
            change_type = "rule_changed"
            explanation = "Итог прежний, но теперь он рассчитан по другому правилу плана."

        presented.append(
            DecisionExplanationChange(
                decision_key=key,
                title=after.title,
                before=before.outcome,
                after=after.outcome,
                explanation=explanation,
                change_type=change_type,
            )
        )
        if len(presented) == MAX_EXPLANATIONS:
            break

    logger.info(
        "decision_trace_diff_presented change_count=%s decision_keys=%s",
        len(presented),
        [item.decision_key for item in presented],
    )
    return presented
