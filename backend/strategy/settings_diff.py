"""Deterministic diff between current strategy snapshot and next preview (Sprint 5.24)."""

from __future__ import annotations

from shopping.normalization import canonical_ingredient_name
from strategy.applied_settings import AppliedSettingsResponse
from strategy.applied_cooking import CookingPreferenceSource
from strategy.explanation import MEAL_TYPE_LABELS, PROTEIN_LABELS
from strategy.models import WeeklyStrategy
from strategy.settings_diff_models import (
    ChangeType,
    ComparisonQuality,
    StrategySettingChange,
    StrategySettingValue,
    StrategySettingsDiff,
)

GOAL_LABELS: dict[str, str] = {
    "healthy": "Правильное питание",
    "home": "Домашняя еда",
    "muscle": "Набор массы",
    "weightloss": "Похудение",
    "restaurant": "Ресторан дома",
    "budget": "Экономно",
}

SOURCE_LABELS: dict[str, str] = {
    "profile": "задано в профиле",
    "learned_preference": "по принятому адаптивному предпочтению",
    "memory": "по истории замен",
    "default": "стандартное правило",
    "inferred": "не сохранён для старого плана",
}

TRACKED_FIELD_COUNT = 17

CHANGE_PRIORITY: dict[str, int] = {
    "excluded_products": 1,
    "availability_avoid_products": 2,
    "prefer_familiar_meals": 3,
    "goal": 2,
    "days": 3,
    "budget": 4,
    "meal_types": 5,
    "preferred_proteins": 6,
    "cooking_time_limit": 7,
    "prefer_faster_meals": 8,
    "cook_days": 9,
    "leftovers_enabled": 10,
    "repeat_breakfasts": 11,
    "repeat_lunches": 12,
    "repeat_dinners": 13,
    "shopping_days": 14,
    "prefer_faster_meals_source": 16,
    "prefer_familiar_meals_source": 17,
}


def build_strategy_settings_diff(
    current_strategy: WeeklyStrategy,
    next_strategy: WeeklyStrategy,
    *,
    current_applied_settings: AppliedSettingsResponse | None,
    next_applied_settings: AppliedSettingsResponse | None,
    comparison_quality: ComparisonQuality = "exact",
) -> StrategySettingsDiff:
    """Pure deterministic diff; no I/O or side effects."""
    changes: list[StrategySettingChange] = []
    changed_keys: set[str] = set()

    def emit(
        key: str,
        *,
        category: str,
        change_type: ChangeType,
        title: str,
        description: str,
        current: StrategySettingValue | None = None,
        next: StrategySettingValue | None = None,
    ) -> None:
        changed_keys.add(key)
        changes.append(
            StrategySettingChange(
                key=key,
                category=category,
                change_type=change_type,
                title=title,
                description=description,
                current=current,
                next=next,
                priority=CHANGE_PRIORITY.get(key, 99),
            )
        )

    _diff_goal(current_strategy, next_strategy, emit)
    _diff_scalar(
        "days",
        "planning",
        current_strategy.days,
        next_strategy.days,
        _format_days_count,
        emit,
    )
    _diff_scalar(
        "budget",
        "planning",
        current_strategy.budget,
        next_strategy.budget,
        _format_budget,
        emit,
    )
    _diff_meal_types(current_strategy, next_strategy, emit)
    _diff_proteins(current_strategy, next_strategy, emit)
    _diff_exclusions(current_strategy, next_strategy, emit)
    _diff_availability_avoid(current_strategy, next_strategy, emit)
    _diff_familiar_meals(current_strategy, next_strategy, current_applied_settings, next_applied_settings, emit)
    _diff_scalar(
        "cooking_time_limit",
        "cooking",
        current_strategy.cooking_time_limit,
        next_strategy.cooking_time_limit,
        _format_cooking_limit,
        emit,
    )
    _diff_faster_preference(current_strategy, next_strategy, current_applied_settings, next_applied_settings, emit)
    _diff_day_list("cook_days", "cooking", current_strategy.cook_days, next_strategy.cook_days, "Готовка", emit)
    _diff_day_list(
        "shopping_days",
        "shopping",
        current_strategy.shopping_days,
        next_strategy.shopping_days,
        "Закупки",
        emit,
    )
    _diff_bool_flag(
        "leftovers_enabled",
        "cooking",
        current_strategy.leftovers_enabled,
        next_strategy.leftovers_enabled,
        "Использование остатков",
        emit,
    )
    _diff_bool_flag(
        "repeat_breakfasts",
        "repeats",
        current_strategy.repeat_breakfasts,
        next_strategy.repeat_breakfasts,
        "Повтор завтраков",
        emit,
    )
    _diff_bool_flag(
        "repeat_lunches",
        "repeats",
        current_strategy.repeat_lunches,
        next_strategy.repeat_lunches,
        "Повтор обедов",
        emit,
    )
    _diff_bool_flag(
        "repeat_dinners",
        "repeats",
        current_strategy.repeat_dinners,
        next_strategy.repeat_dinners,
        "Повтор ужинов",
        emit,
    )

    changes.sort(key=lambda item: (item.priority, item.key))
    unchanged_count = max(0, TRACKED_FIELD_COUNT - len(changed_keys))

    return StrategySettingsDiff(
        has_changes=len(changes) > 0,
        changes=changes,
        unchanged_count=unchanged_count,
        comparison_quality=comparison_quality,
    )


def _diff_goal(
    current: WeeklyStrategy,
    next_: WeeklyStrategy,
    emit,
) -> None:
    if current.goal == next_.goal:
        return
    emit(
        "goal",
        category="planning",
        change_type="changed",
        title="Цель питания",
        description=(
            f"Цель изменится с «{GOAL_LABELS.get(current.goal, current.goal)}» "
            f"на «{GOAL_LABELS.get(next_.goal, next_.goal)}»."
        ),
        current=StrategySettingValue(
            display_value=GOAL_LABELS.get(current.goal, current.goal),
            raw_value=current.goal,
        ),
        next=StrategySettingValue(
            display_value=GOAL_LABELS.get(next_.goal, next_.goal),
            raw_value=next_.goal,
        ),
    )


def _diff_scalar(key, category, current_val, next_val, formatter, emit) -> None:
    if current_val == next_val:
        return
    emit(
        key,
        category=category,
        change_type="changed",
        title=_title_for_key(key),
        description=f"{_title_for_key(key)}: {formatter(current_val)} → {formatter(next_val)}.",
        current=StrategySettingValue(display_value=formatter(current_val), raw_value=current_val),
        next=StrategySettingValue(display_value=formatter(next_val), raw_value=next_val),
    )


def _diff_meal_types(current: WeeklyStrategy, next_: WeeklyStrategy, emit) -> None:
    current_types = sorted(current.meal_types)
    next_types = sorted(next_.meal_types)
    if current_types == next_types:
        return
    current_labels = [_meal_label(value) for value in current_types]
    next_labels = [_meal_label(value) for value in next_types]
    emit(
        "meal_types",
        category="planning",
        change_type="changed",
        title="Приёмы пищи",
        description=(
            f"Приёмы пищи изменятся с {_join_ru(current_labels)} на {_join_ru(next_labels)}."
        ),
        current=StrategySettingValue(display_value=_join_ru(current_labels), raw_value=current_types),
        next=StrategySettingValue(display_value=_join_ru(next_labels), raw_value=next_types),
    )


def _diff_proteins(current: WeeklyStrategy, next_: WeeklyStrategy, emit) -> None:
    current_set = set(current.preferred_proteins)
    next_set = set(next_.preferred_proteins)
    if current_set == next_set:
        return

    added = sorted(next_set - current_set)
    removed = sorted(current_set - next_set)
    parts: list[str] = []
    if removed:
        labels = [_protein_label(value) for value in removed]
        if len(labels) == 1:
            parts.append(f"{labels[0]} больше не будет использоваться как предпочтительный источник белка.")
        else:
            parts.append(
                "Некоторые источники белка больше не будут предпочтительными: "
                f"{_join_ru(labels)}."
            )
    if added:
        labels = [_protein_label(value) for value in added]
        if len(labels) == 1:
            parts.append(f"{labels[0]} будет добавлен как предпочтительный источник белка.")
        else:
            parts.append(f"Будут добавлены предпочтительные источники белка: {_join_ru(labels)}.")

    change_type: ChangeType = "changed"
    if added and not removed:
        change_type = "added"
    elif removed and not added:
        change_type = "removed"

    emit(
        "preferred_proteins",
        category="planning",
        change_type=change_type,
        title="Предпочтительные источники белка",
        description=" ".join(parts),
        current=StrategySettingValue(
            display_value=_join_ru([_protein_label(v) for v in sorted(current_set)]),
            raw_value=sorted(current_set),
        ),
        next=StrategySettingValue(
            display_value=_join_ru([_protein_label(v) for v in sorted(next_set)]),
            raw_value=sorted(next_set),
        ),
    )


def _diff_familiar_meals(
    current: WeeklyStrategy,
    next_: WeeklyStrategy,
    current_applied: AppliedSettingsResponse | None,
    next_applied: AppliedSettingsResponse | None,
    emit,
) -> None:
    current_enabled = current.prefer_familiar_meals
    next_enabled = next_.prefer_familiar_meals
    current_source = (
        current_applied.planning.familiar_meals_source
        if current_applied and current_applied.planning
        else "inferred"
    )
    next_source = (
        next_applied.planning.familiar_meals_source
        if next_applied and next_applied.planning
        else "inferred"
    )
    if current_enabled == next_enabled:
        if (
            current_source != next_source
            and current_source != "inferred"
            and next_source != "inferred"
        ):
            emit(
                "prefer_familiar_meals_source",
                category="planning",
                change_type="source_changed",
                title="Источник предпочтения знакомых блюд",
                description=(
                    "Источник предпочтения изменится: "
                    f"{SOURCE_LABELS.get(next_source, next_source)} вместо "
                    f"{SOURCE_LABELS.get(current_source, current_source)}."
                ),
                current=StrategySettingValue(
                    display_value=SOURCE_LABELS.get(
                        current_source, current_source
                    ),
                    raw_value=current_enabled,
                    source=current_source,
                ),
                next=StrategySettingValue(
                    display_value=SOURCE_LABELS.get(next_source, next_source),
                    raw_value=next_enabled,
                    source=next_source,
                ),
            )
        return

    if next_enabled and not current_enabled:
        title = "Знакомые блюда"
        description = "Следующий план будет отдавать предпочтение более знакомым блюдам."
        change_type: ChangeType = "added"
    else:
        title = "Знакомые блюда"
        description = "Предпочтение более знакомых блюд отключено."
        change_type = "removed"

    emit(
        "prefer_familiar_meals",
        category="planning",
        change_type=change_type,
        title=title,
        description=description,
        current=StrategySettingValue(
            display_value=_bool_label(current_enabled),
            raw_value=current_enabled,
            source=current_source,
        ),
        next=StrategySettingValue(
            display_value=_bool_label(next_enabled),
            raw_value=next_enabled,
            source=next_source,
        ),
    )


def _diff_availability_avoid(current: WeeklyStrategy, next_: WeeklyStrategy, emit) -> None:
    current_set = {
        canonical_ingredient_name(item)
        for item in current.availability_avoid_products
        if item.strip()
    }
    next_set = {
        canonical_ingredient_name(item)
        for item in next_.availability_avoid_products
        if item.strip()
    }
    current_set = {item for item in current_set if item}
    next_set = {item for item in next_set if item}
    if current_set == next_set:
        return

    added_count = len(next_set - current_set)
    removed_count = len(current_set - next_set)
    parts: list[str] = []
    if added_count == 1:
        parts.append(
            "В следующем плане будет учтено ещё одно наблюдение о доступности продуктов."
        )
    elif added_count > 1:
        parts.append(
            f"В следующем плане будет учтено ещё {added_count} наблюдения о доступности продуктов."
        )
    if removed_count == 1:
        parts.append("Одно наблюдение о доступности продуктов больше не учитывается.")
    elif removed_count > 1:
        parts.append(
            f"{removed_count} наблюдения о доступности продуктов больше не учитываются."
        )

    change_type: ChangeType = "changed"
    if added_count and not removed_count:
        change_type = "added"
    elif removed_count and not added_count:
        change_type = "removed"

    emit(
        "availability_avoid_products",
        category="behavior",
        change_type=change_type,
        title="Доступность продуктов",
        description=" ".join(parts),
        current=StrategySettingValue(
            display_value=_availability_summary(len(current_set)),
            raw_value=sorted(current_set),
        ),
        next=StrategySettingValue(
            display_value=_availability_summary(len(next_set)),
            raw_value=sorted(next_set),
        ),
    )


def _diff_exclusions(current: WeeklyStrategy, next_: WeeklyStrategy, emit) -> None:
    current_set = {item.strip().lower() for item in current.excluded_products if item.strip()}
    next_set = {item.strip().lower() for item in next_.excluded_products if item.strip()}
    if current_set == next_set:
        return

    added_count = len(next_set - current_set)
    removed_count = len(current_set - next_set)
    parts: list[str] = []
    if added_count:
        parts.append(_exclusion_count_phrase(added_count, added=True))
    if removed_count:
        parts.append(_exclusion_count_phrase(removed_count, added=False))

    change_type: ChangeType = "changed"
    if added_count and not removed_count:
        change_type = "added"
    elif removed_count and not added_count:
        change_type = "removed"

    emit(
        "excluded_products",
        category="constraints",
        change_type=change_type,
        title="Ограничения по продуктам",
        description=" ".join(parts),
        current=StrategySettingValue(
            display_value=_exclusion_summary(len(current_set)),
            raw_value=sorted(current_set),
        ),
        next=StrategySettingValue(
            display_value=_exclusion_summary(len(next_set)),
            raw_value=sorted(next_set),
        ),
    )


def _diff_faster_preference(
    current: WeeklyStrategy,
    next_: WeeklyStrategy,
    current_applied: AppliedSettingsResponse | None,
    next_applied: AppliedSettingsResponse | None,
    emit,
) -> None:
    current_faster = _applied_faster_bool(current, current_applied)
    next_faster = _applied_faster_bool(next_, next_applied)
    current_source = _applied_faster_source(current, current_applied)
    next_source = _applied_faster_source(next_, next_applied)

    if current_faster != next_faster:
        emit(
            "prefer_faster_meals",
            category="cooking",
            change_type="changed",
            title="Предпочтение скорости",
            description=(
                f"Более быстрые блюда: {_bool_label(current_faster)} → {_bool_label(next_faster)}."
            ),
            current=StrategySettingValue(
                display_value=_bool_label(current_faster),
                raw_value=current_faster,
                source=current_source,
            ),
            next=StrategySettingValue(
                display_value=_bool_label(next_faster),
                raw_value=next_faster,
                source=next_source,
            ),
        )
    elif current_source != next_source and current_source != "inferred" and next_source != "inferred":
        emit(
            "prefer_faster_meals_source",
            category="cooking",
            change_type="source_changed",
            title="Источник предпочтения скорости",
            description=(
                "Предпочтение быстрых блюд теперь "
                f"{SOURCE_LABELS.get(next_source, next_source)}, "
                f"а не {SOURCE_LABELS.get(current_source, current_source)}."
            ),
            current=StrategySettingValue(
                display_value=SOURCE_LABELS.get(current_source, current_source),
                raw_value=current_faster,
                source=current_source,
            ),
            next=StrategySettingValue(
                display_value=SOURCE_LABELS.get(next_source, next_source),
                raw_value=next_faster,
                source=next_source,
            ),
        )


def _diff_day_list(key, category, current_days, next_days, title_prefix, emit) -> None:
    if sorted(current_days) == sorted(next_days):
        return
    emit(
        key,
        category=category,
        change_type="changed",
        title=_title_for_key(key),
        description=(
            f"{title_prefix} изменятся с дней {_format_day_list(current_days)} "
            f"на дни {_format_day_list(next_days)}."
        ),
        current=StrategySettingValue(
            display_value=_format_day_list(current_days),
            raw_value=[str(day) for day in sorted(current_days)],
        ),
        next=StrategySettingValue(
            display_value=_format_day_list(next_days),
            raw_value=[str(day) for day in sorted(next_days)],
        ),
    )


def _diff_bool_flag(key, category, current_val, next_val, title, emit) -> None:
    if current_val == next_val:
        return
    emit(
        key,
        category=category,
        change_type="changed",
        title=title,
        description=f"{title}: {_bool_label(current_val)} → {_bool_label(next_val)}.",
        current=StrategySettingValue(display_value=_bool_label(current_val), raw_value=current_val),
        next=StrategySettingValue(display_value=_bool_label(next_val), raw_value=next_val),
    )


def _applied_faster_bool(strategy: WeeklyStrategy, applied: AppliedSettingsResponse | None) -> bool:
    if applied is not None:
        return applied.cooking.prefer_faster_meals
    return strategy.prefer_faster_meals


def _applied_faster_source(
    strategy: WeeklyStrategy,
    applied: AppliedSettingsResponse | None,
) -> CookingPreferenceSource:
    if applied is not None:
        return applied.cooking.preference_source
    return "inferred"


def _title_for_key(key: str) -> str:
    return {
        "days": "Количество дней",
        "budget": "Плановый бюджет",
        "cooking_time_limit": "Максимальное время активной готовки",
        "cook_days": "Дни готовки",
        "shopping_days": "Дни закупок",
    }.get(key, key)


def _format_days_count(value: int) -> str:
    return f"{value} {_plural_days(value)}"


def _format_budget(value: float) -> str:
    amount = int(value) if float(value).is_integer() else value
    return f"{amount:,}".replace(",", " ") + " ₽"


def _format_cooking_limit(value: int) -> str:
    return f"до {value} минут"


def _format_day_list(days: list[int]) -> str:
    return _join_ru([str(day) for day in sorted(days)])


def _bool_label(value: bool) -> str:
    return "включено" if value else "выключено"


def _meal_label(value: str) -> str:
    return MEAL_TYPE_LABELS.get(value, value)


def _protein_label(value: str) -> str:
    return PROTEIN_LABELS.get(value, value)


def _join_ru(items: list[str]) -> str:
    if not items:
        return "—"
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} и {items[1]}"
    return ", ".join(items[:-1]) + f" и {items[-1]}"


def _plural_days(count: int) -> str:
    if count % 10 == 1 and count % 100 != 11:
        return "день"
    if 2 <= count % 10 <= 4 and not (12 <= count % 100 <= 14):
        return "дня"
    return "дней"


def _exclusion_count_phrase(count: int, *, added: bool) -> str:
    if added:
        if count == 1:
            return "В следующем плане будет учтено ещё одно ограничение по продуктам."
        return f"В следующем плане будет учтено ещё {count} ограничения по продуктам."
    if count == 1:
        return "Одно ограничение по продуктам больше не будет учитываться."
    return f"{count} ограничения по продуктам больше не будут учитываться."


def _exclusion_summary(count: int) -> str:
    if count == 0:
        return "нет ограничений"
    if count == 1:
        return "1 ограничение"
    return f"{count} ограничения"


def _availability_summary(count: int) -> str:
    if count == 0:
        return "не учитываются"
    if count == 1:
        return "учтено 1 наблюдение"
    return f"учтено {count} наблюдения"
