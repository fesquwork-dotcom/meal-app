"""Allowlisted presentation for Learned Preference effectiveness."""

from __future__ import annotations

from learned_preferences.effectiveness_models import (
    LearnedPreferenceEffectiveness,
    LearnedPreferenceEffectivenessLimitation,
    LearnedPreferenceEffectivenessResponse,
    LearnedPreferenceEffectivenessSummaryCode,
)

_TITLES: dict[LearnedPreferenceEffectivenessSummaryCode, str] = {
    "INSUFFICIENT_DATA": "Пока собираем данные",
    "EMERGING_POSITIVE": "Есть первые положительные признаки",
    "EFFECTIVE_STABLE": "Показывает устойчиво положительный результат",
    "NEUTRAL_MIXED": "Результаты смешанные",
    "INEFFECTIVE_REPLACEMENTS": "Стоит проверить это предпочтение",
    "UNSUPPORTED_TYPE": "Пока собираем данные",
}

_SUMMARIES: dict[LearnedPreferenceEffectivenessSummaryCode, str] = {
    "INSUFFICIENT_DATA": (
        "Пока недостаточно завершённых планов, чтобы оценить это "
        "адаптивное предпочтение."
    ),
    "EMERGING_POSITIVE": (
        "Есть первые признаки, что это предпочтение подходит вам."
    ),
    "EFFECTIVE_STABLE": (
        "На нескольких завершённых планах это предпочтение показывало "
        "устойчиво положительный результат."
    ),
    "NEUTRAL_MIXED": (
        "Результаты пока смешанные — явного улучшения или ухудшения не видно."
    ),
    "INEFFECTIVE_REPLACEMENTS": (
        "После применения этого предпочтения планы всё ещё часто "
        "требовали замен."
    ),
    "UNSUPPORTED_TYPE": (
        "Для этого типа предпочтения пока нет достаточных данных "
        "для оценки эффективности."
    ),
}

_LIMITATION_TEXTS: dict[LearnedPreferenceEffectivenessLimitation, str] = {
    "SMALL_SAMPLE": "Выборка пока небольшая — вывод предварительный.",
    "NO_CONTROL_GROUP": (
        "Нет контрольной группы: другие настройки тоже могли повлиять."
    ),
    "LEGACY_SNAPSHOTS_EXCLUDED": (
        "Планы без записи о применении предпочтения не учитываются."
    ),
    "UNSUPPORTED_TYPE": (
        "Этот тип предпочтения пока не оценивается по завершённым планам."
    ),
    "MIXED_EVIDENCE": "Положительные и отрицательные признаки встречаются вместе.",
    "ABSENT_POSITIVE_NOT_NEGATIVE": (
        "Отсутствие отметок не считается доказательством, что предпочтение "
        "не работает."
    ),
}


def _evidence_text(count: int) -> str:
    if count <= 0:
        return "Пока нет завершённых планов, где предпочтение применялось."
    if count == 1:
        return (
            "Основано на 1 завершённом плане, где предпочтение "
            "действительно применялось."
        )
    if 2 <= count <= 4:
        return (
            f"Основано на {count} завершённых планах, где предпочтение "
            "действительно применялось."
        )
    return (
        f"Основано на {count} завершённых планах, где предпочтение "
        "действительно применялось."
    )


def present_effectiveness(
    result: LearnedPreferenceEffectiveness,
) -> LearnedPreferenceEffectivenessResponse:
    return LearnedPreferenceEffectivenessResponse(
        status=result.status,
        confidence=result.confidence,
        evidence_plans=result.evidence_plans,
        generation=result.generation,
        title=_TITLES[result.summary_code],
        summary=_SUMMARIES[result.summary_code],
        evidence_text=_evidence_text(result.evidence_plans),
        limitations=[
            _LIMITATION_TEXTS[item]
            for item in result.limitations
            if item in _LIMITATION_TEXTS
        ],
    )
