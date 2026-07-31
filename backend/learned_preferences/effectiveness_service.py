"""Read-only orchestration for Learned Preference effectiveness."""

from __future__ import annotations

import logging

from learned_preferences.effectiveness import (
    evaluate_learned_preference_effectiveness,
)
from learned_preferences.effectiveness_models import (
    LearnedPreferenceEffectivenessResponse,
)
from learned_preferences.effectiveness_presentation import present_effectiveness
from learned_preferences.models import LearnedPreferenceType
from learned_preferences.observation_repository import (
    LearnedPreferenceObservationRepository,
)

logger = logging.getLogger(__name__)

_EVALUABLE = frozenset({"prefer_familiar_meals", "prefer_fast_meals"})


class LearnedPreferenceEffectivenessService:
    def __init__(
        self,
        *,
        observation_repository: LearnedPreferenceObservationRepository
        | None = None,
    ) -> None:
        self._observations = (
            observation_repository or LearnedPreferenceObservationRepository()
        )

    async def get_effectiveness(
        self, user_id: int, preference_type: LearnedPreferenceType
    ) -> LearnedPreferenceEffectivenessResponse | None:
        try:
            observations = await self._observations.load_applied_plan_observations(
                user_id, preference_type
            )
            result = evaluate_learned_preference_effectiveness(
                preference_type, observations
            )
            payload = present_effectiveness(result)
            logger.info(
                "learned_preference_effectiveness_evaluated type=%s "
                "status=%s confidence=%s evidence_plans=%s "
                "positive=%s negative=%s",
                preference_type,
                result.status,
                result.confidence,
                result.evidence_plans,
                result.positive_evidence_count,
                result.negative_evidence_count,
            )
            return payload
        except Exception as exc:
            logger.warning(
                "learned_preference_effectiveness_unavailable type=%s "
                "error_type=%s",
                preference_type,
                type(exc).__name__,
            )
            return None

    async def get_all_effectiveness(
        self, user_id: int, preference_types: list[LearnedPreferenceType]
    ) -> dict[str, LearnedPreferenceEffectivenessResponse | None]:
        results: dict[str, LearnedPreferenceEffectivenessResponse | None] = {}
        for preference_type in preference_types:
            if preference_type not in _EVALUABLE:
                results[preference_type] = None
                continue
            results[preference_type] = await self.get_effectiveness(
                user_id, preference_type
            )
        return results
