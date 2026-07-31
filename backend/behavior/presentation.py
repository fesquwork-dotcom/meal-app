"""Deterministic user-facing titles and descriptions for behavior insights."""

from __future__ import annotations

from dataclasses import dataclass

from behavior.constants import BehaviorInsightType
from behavior.records import BehaviorInsightRecord


@dataclass(frozen=True)
class BehaviorInsightPresentation:
    title: str
    description: str


def present_behavior_insight(insight: BehaviorInsightRecord) -> BehaviorInsightPresentation:
    insight_type = BehaviorInsightType(insight.insight_type)
    evidence_note = _evidence_note(insight.evidence_count)

    if insight_type == BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT:
        return BehaviorInsightPresentation(
            title="Вы несколько раз заменяли один и тот же рецепт",
            description=(
                "Мы заметили повторяющиеся замены и можем учитывать этот паттерн "
                "после вашего подтверждения. "
                f"{evidence_note}"
            ).strip(),
        )

    if insight_type == BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION:
        label = (insight.target_label or "").strip()
        if label:
            return BehaviorInsightPresentation(
                title="Этот продукт несколько раз был недоступен",
                description=(
                    f"{label} регулярно оказывается недоступен при замене блюд. "
                    f"{evidence_note}"
                ).strip(),
            )
        return BehaviorInsightPresentation(
            title="Некоторые продукты регулярно оказываются недоступны",
            description=(
                "Мы заметили повторяющиеся замены из-за недоступности продуктов. "
                f"{evidence_note}"
            ).strip(),
        )

    if insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE:
        return BehaviorInsightPresentation(
            title="Вы часто меняете блюда в готовом плане",
            description=(
                "Подтвердите наблюдение, если хотите, чтобы приложение учитывало "
                "это в будущем. "
                f"{evidence_note}"
            ).strip(),
        )

    return BehaviorInsightPresentation(
        title="Мы заметили повторяющийся паттерн",
        description=evidence_note,
    )


def _evidence_note(evidence_count: int) -> str:
    if evidence_count <= 0:
        return ""
    return f"Замечено {evidence_count} раз."
