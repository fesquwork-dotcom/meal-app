"""Behavior recommendation capability helpers (Sprint 5.27)."""

from __future__ import annotations

from enum import StrEnum

from behavior.constants import BehaviorInsightStatus, BehaviorInsightType
from behavior.records import BehaviorInsightRecord
from planning_preferences import PREFER_FAMILIAR_MEALS_RECOMMENDATION_KEY


class BehaviorRecommendationCapability(StrEnum):
    ALREADY_APPLIES = "already_applies"
    STORED_ONLY = "stored_only"
    CAN_ENABLE_FAMILIAR_MEALS = "can_enable_familiar_meals"


def get_behavior_recommendation_capability(
    insight_type: BehaviorInsightType | str,
) -> BehaviorRecommendationCapability:
    normalized = (
        insight_type.value if isinstance(insight_type, BehaviorInsightType) else str(insight_type)
    )
    if normalized == BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION.value:
        return BehaviorRecommendationCapability.ALREADY_APPLIES
    if normalized == BehaviorInsightType.HIGH_REPLACEMENT_RATE.value:
        return BehaviorRecommendationCapability.CAN_ENABLE_FAMILIAR_MEALS
    return BehaviorRecommendationCapability.STORED_ONLY


def recommendation_key_for_insight(insight: BehaviorInsightRecord) -> str | None:
    if insight.insight_type != BehaviorInsightType.HIGH_REPLACEMENT_RATE.value:
        return None
    return PREFER_FAMILIAR_MEALS_RECOMMENDATION_KEY


def can_apply_recommendation(
    insight: BehaviorInsightRecord,
    *,
    profile_prefer_familiar_meals: bool | None,
) -> bool:
    if insight.status != BehaviorInsightStatus.CONFIRMED.value:
        return False
    if get_behavior_recommendation_capability(insight.insight_type) != (
        BehaviorRecommendationCapability.CAN_ENABLE_FAMILIAR_MEALS
    ):
        return False
    if insight.recommendation_applied_at:
        return False
    if profile_prefer_familiar_meals is True:
        return False
    return True
