"""Deterministic Russian presentation texts for trend metrics.

All texts come from a fixed allowlist. No LLM, no interpolation of raw
values except the pre-formatted safe percentage for established metrics.
"""

from __future__ import annotations

from trends.models import MetricId, TrendConfidenceStatus, TrendMetricStatus

METRIC_TITLES: dict[MetricId, str] = {
    "replacement_rate": "Замены блюд",
    "positive_completion": "Подтверждённые успехи",
    "decision_health": "Здоровье решений",
    "recommendation_effectiveness": "Эффект рекомендаций",
    "preference_stability": "Стабильность настроек",
}

# Aggregate-only source labels; never table or column names.
METRIC_SOURCES: dict[MetricId, str] = {
    "replacement_rate": "история замен",
    "positive_completion": "ваши отметки",
    "decision_health": "итоги решений",
    "recommendation_effectiveness": "принятые рекомендации",
    "preference_stability": "настройки планов",
}

CAPABILITY_NOTE = (
    "Эта метрика рассчитывается только для планов, "
    "созданных после обновления приложения."
)

INSUFFICIENT_TEXT = "Пока недостаточно данных."

_EMERGING_TEXTS: dict[TrendMetricStatus, str] = {
    "improving": "Есть первые признаки улучшения.",
    "worsening": "Есть первые признаки ухудшения.",
    "stable": "Заметных изменений пока нет.",
    "volatile": "Настройки пока меняются часто.",
    "insufficient_data": INSUFFICIENT_TEXT,
}

_ESTABLISHED_TEXTS: dict[MetricId, dict[TrendMetricStatus, str]] = {
    "replacement_rate": {
        "improving": "Замен стало меньше.",
        "worsening": "Замен стало больше.",
        "stable": "Число замен не изменилось.",
    },
    "positive_completion": {
        "improving": "Подтверждённых успехов стало больше.",
        "worsening": "Подтверждённых успехов стало меньше.",
        "stable": "Доля подтверждённых успехов не изменилась.",
    },
    "decision_health": {
        "improving": "Решения стали срабатывать чаще.",
        "worsening": "Решения стали срабатывать реже.",
        "stable": "Качество решений не изменилось.",
    },
    "recommendation_effectiveness": {
        "improving": "После принятой рекомендации замен стало меньше.",
        "worsening": "После принятой рекомендации замен стало больше.",
        "stable": "Принятая рекомендация пока не изменила число замен.",
    },
    "preference_stability": {
        "stable": "Настройки остаются стабильными.",
        "volatile": "Настройки меняются часто.",
    },
}


def summary_text(
    metric_id: MetricId,
    status: TrendMetricStatus,
    confidence: TrendConfidenceStatus,
) -> str:
    if confidence == "insufficient_data" or status == "insufficient_data":
        return INSUFFICIENT_TEXT
    if confidence == "emerging":
        return _EMERGING_TEXTS[status]
    return _ESTABLISHED_TEXTS[metric_id].get(status, INSUFFICIENT_TEXT)


def format_percent(rate: float) -> str:
    return f"{round(rate * 100)}%"
