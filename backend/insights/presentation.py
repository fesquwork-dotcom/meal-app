"""Allowlisted user-facing texts for deterministic insights."""

from __future__ import annotations

from insights.models import InsightId

INSIGHT_TITLES: dict[InsightId, str] = {
    "replacement_health": "Замены стали реже",
    "replacement_cost": "Как замены влияют на стоимость",
    "preference_stability": "Настройки стали устойчивее",
    "recommendation_effectiveness": "Эффект принятых рекомендаций",
    "positive_completion": "Планы чаще завершаются успешно",
}

INSUFFICIENT_SUMMARIES: dict[InsightId, str] = {
    "replacement_health": "Пока недостаточно истории замен и итогов решений.",
    "replacement_cost": "Пока недостаточно сопоставимых планов после замен.",
    "preference_stability": "Пока недостаточно истории настроек и итогов решений.",
    "recommendation_effectiveness": "Пока недостаточно данных после принятых рекомендаций.",
    "positive_completion": "Пока недостаточно подтверждённых завершений планов.",
}

# Trend-backed rules reuse TrendMetric.summary_text directly. This is the only
# new conclusion template in v1 because Plan Delta has no presentation text.
COST_DECREASE_SUMMARY = "После замен стоимость плана обычно уменьшается."

