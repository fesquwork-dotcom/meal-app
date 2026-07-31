"""Insight Transparency Builder (Sprint 8.2).

Turns InsightEvidence into allowlisted user-facing texts. The only dynamic
value ever interpolated is the completed-plans count; everything else is a
fixed template keyed by an enum.
"""

from __future__ import annotations

from insights.evidence_models import (
    InsightEvidence,
    InsightLimitation,
    InsightTransparency,
)
from insights.models import Insight

TRANSPARENCY_TITLE = "Почему мы так считаем"

PROOF_COLLECTING_TEXT = "Пока собираем данные."

COVERAGE_TEXTS: dict[str, str] = {
    "complete": "Данных достаточно для устойчивого вывода.",
    "partial": "Данных пока хватает только для предварительного вывода.",
    "insufficient": "Для надёжного вывода нужно больше завершённых планов.",
}

AVAILABILITY_LIMITED_TEXT = "Есть данные только после обновления приложения."

LIMITATION_TEXTS: dict[InsightLimitation, str] = {
    "legacy_strategies": "Некоторые старые планы не содержат необходимых данных.",
    "positive_events_missing": "Подтверждённых отметок о выполнении пока нет.",
    "not_enough_completed_plans": (
        "Пока недостаточно завершённых планов для устойчивого вывода."
    ),
    "budget_data_unavailable": "Данные о стоимости пока недоступны.",
    "menuplan_not_persisted": "Старые планы не сохранены на сервере.",
    "decision_snapshot_missing": "Часть планов не содержит снимка решений.",
    "outcome_snapshot_missing": "Итоги решений пока не рассчитаны.",
}


def _plural_plans_prepositional(count: int) -> str:
    remainder_100 = count % 100
    remainder_10 = count % 10
    if remainder_10 == 1 and remainder_100 != 11:
        return "плане"
    return "планах"


def _proof_text(evidence: InsightEvidence) -> str:
    if evidence.coverage.status == "insufficient":
        return PROOF_COLLECTING_TEXT
    count = evidence.completed_strategies
    return (
        f"Основано на последних {count} завершённых "
        f"{_plural_plans_prepositional(count)}."
    )


def _availability_text(evidence: InsightEvidence) -> str | None:
    available_since = evidence.coverage.available_since
    oldest = evidence.coverage.oldest_plan_date
    # Data for this insight starts later than the user's plan history: the
    # underlying capability appeared with an app update.
    if available_since is not None and oldest is not None and available_since > oldest:
        return AVAILABILITY_LIMITED_TEXT
    return None


def build_insight_transparency(
    insight: Insight,
    evidence: InsightEvidence,
) -> InsightTransparency:
    return InsightTransparency(
        title=TRANSPARENCY_TITLE,
        proof_text=_proof_text(evidence),
        coverage_text=COVERAGE_TEXTS[evidence.coverage.status],
        availability_text=_availability_text(evidence),
        limitations_text=[
            LIMITATION_TEXTS[limitation] for limitation in evidence.limitations
        ],
    )
