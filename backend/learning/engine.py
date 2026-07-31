"""Pure, deterministic Decision Learning rules.

The engine proposes profile changes; it never persists or applies them.
No clock, database, LLM, Decision Engine, or raw identifiers are used here.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cooking_preferences import parse_cooking_preferences
from decision.outcome import DecisionOutcome, DecisionOutcomeCollection
from learning.models import (
    LEARNING_RULE_VERSION,
    LearningRecommendation,
    LearningRecommendationCollection,
    LearningRecommendationType,
    RecommendedProfilePatch,
)
from planning_preferences import parse_planning_preferences


class LearningEvidence(BaseModel):
    """Privacy-safe aggregates for one finalized strategy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    replacement_count: int = Field(ge=0)
    planned_meal_count: int = Field(ge=0)
    faster_replacement_count: int = Field(ge=0)
    suited_meal_count: int = Field(ge=0)
    cooked_meal_count: int = Field(ge=0)
    decision_prefer_familiar: bool | None = None
    decision_prefer_faster: bool | None = None
    shopping_completed: bool = False
    plan_completed: bool = False

    @property
    def replacement_rate(self) -> float:
        if self.planned_meal_count <= 0:
            return 0.0
        return min(1.0, self.replacement_count / self.planned_meal_count)


_TEMPLATES: dict[
    LearningRecommendationType, tuple[str, str, str, str, str]
] = {
    "profile_enable_prefer_familiar_meals": (
        "Попробовать знакомые блюда",
        "Последний план часто требовал замен при отключённом предпочтении знакомых блюд.",
        "Результат плана показал высокую долю замен.",
        "Знакомые варианты могут уменьшить число замен в следующем плане.",
        "Текущий план и другие настройки профиля не изменятся.",
    ),
    "profile_disable_prefer_familiar_meals": (
        "Ослабить предпочтение знакомых блюд",
        "Предпочтение знакомых блюд не дало устойчивого результата.",
        "План часто требовал замен, а положительных подтверждений этой настройки нет.",
        "Следующий план сможет предлагать более широкий набор вариантов.",
        "Текущий план и другие настройки профиля не изменятся.",
    ),
    "profile_enable_prefer_faster_meals": (
        "Попробовать более быстрые блюда",
        "Во время последнего плана регулярно требовались более быстрые замены.",
        "Результаты плана подтверждают повторяющуюся нехватку времени на блюда.",
        "Следующий план будет чаще выбирать быстрые варианты в текущем лимите.",
        "Лимит времени и текущий план не изменятся.",
    ),
    "profile_disable_prefer_faster_meals": (
        "Отключить предпочтение быстрых блюд",
        "Предпочтение быстрых блюд не дало устойчивого результата.",
        "План часто требовал замен, а положительных подтверждений этой настройки нет.",
        "Следующий план сможет использовать больше вариантов в текущем лимите времени.",
        "Лимит времени и текущий план не изменятся.",
    ),
    "profile_adjust_cooking_time": (
        "Изменить лимит времени на готовку",
        "Несколько завершённых планов показали устойчивую нехватку времени.",
        "Рекомендация основана на повторяющихся подтверждённых результатах.",
        "Новый лимит расширит выбор подходящих блюд следующего плана.",
        "Текущий план не изменится.",
    ),
}


def _outcome(
    outcomes: DecisionOutcomeCollection, decision_key: str
) -> DecisionOutcome | None:
    return next(
        (item for item in outcomes.outcomes if item.decision_key == decision_key),
        None,
    )


def build_learning_recommendation(
    recommendation_type: LearningRecommendationType,
    *,
    recommendation_id: str | None = None,
    decision_key: str,
    confidence: str,
    patch: RecommendedProfilePatch,
    status: str = "candidate",
    created_at: str | None = None,
) -> LearningRecommendation:
    title, summary, reason, expected_effect, unchanged = _TEMPLATES[
        recommendation_type
    ]
    return LearningRecommendation(
        # A draft id is deterministic and replaced by a durable repository id.
        recommendation_id=(
            recommendation_id
            or f"draft:v{LEARNING_RULE_VERSION}:{recommendation_type}"
        ),
        recommendation_type=recommendation_type,
        decision_key=decision_key,
        status=status,  # type: ignore[arg-type]
        confidence=confidence,  # type: ignore[arg-type]
        created_at=created_at,
        title=title,
        summary=summary,
        reason=reason,
        expected_effect=expected_effect,
        what_will_not_change=unchanged,
        recommended_profile_patch=patch,
    )


def build_learning_recommendations(
    outcomes: DecisionOutcomeCollection,
    evidence: LearningEvidence,
    profile: dict[str, object],
) -> LearningRecommendationCollection:
    """Build recommendations from one immutable outcome snapshot.

    Cooking-time adjustment is intentionally not generated in rule version 1:
    DecisionOutcome does not yet evaluate ``cooking.time_limit``. Supporting
    the type without inventing evidence preserves the trust boundary.
    """
    recommendations: list[LearningRecommendation] = []
    planning = parse_planning_preferences(profile)
    cooking = parse_cooking_preferences(profile)
    confidence = (
        "strong"
        if evidence.replacement_rate > 0.35 and evidence.replacement_count >= 3
        else "moderate"
    )

    familiar = _outcome(outcomes, "planning.prefer_familiar_meals")
    if familiar is not None and familiar.status == "unsuccessful":
        if (
            evidence.decision_prefer_familiar is False
            and planning.prefer_familiar_meals is False
            and (
            familiar.result == "high_replacement_rate"
            or evidence.replacement_rate > 0.35
            )
        ):
            recommendations.append(
                build_learning_recommendation(
                    "profile_enable_prefer_familiar_meals",
                    decision_key=familiar.decision_key,
                    confidence=confidence,
                    patch=RecommendedProfilePatch(
                        planning_preferences={"prefer_familiar_meals": True}
                    ),
                )
            )
        elif (
            evidence.decision_prefer_familiar is True
            and planning.prefer_familiar_meals is True
            and evidence.suited_meal_count == 0
            and not evidence.plan_completed
        ):
            recommendations.append(
                build_learning_recommendation(
                    "profile_disable_prefer_familiar_meals",
                    decision_key=familiar.decision_key,
                    confidence=confidence,
                    patch=RecommendedProfilePatch(
                        planning_preferences={"prefer_familiar_meals": False}
                    ),
                )
            )

    faster = _outcome(outcomes, "cooking.prefer_faster")
    if faster is not None and faster.status == "unsuccessful":
        if (
            evidence.decision_prefer_faster is False
            and cooking.prefer_faster_meals is False
            and (
            faster.result == "faster_replacements_persisted"
            or evidence.faster_replacement_count >= 2
            )
        ):
            recommendations.append(
                build_learning_recommendation(
                    "profile_enable_prefer_faster_meals",
                    decision_key=faster.decision_key,
                    confidence=confidence,
                    patch=RecommendedProfilePatch(
                        cooking_preferences={"prefer_faster_meals": True}
                    ),
                )
            )
        elif (
            evidence.decision_prefer_faster is True
            and cooking.prefer_faster_meals is True
            and evidence.suited_meal_count == 0
            and not evidence.plan_completed
        ):
            recommendations.append(
                build_learning_recommendation(
                    "profile_disable_prefer_faster_meals",
                    decision_key=faster.decision_key,
                    confidence=confidence,
                    patch=RecommendedProfilePatch(
                        cooking_preferences={"prefer_faster_meals": False}
                    ),
                )
            )

    return LearningRecommendationCollection(recommendations=recommendations)
