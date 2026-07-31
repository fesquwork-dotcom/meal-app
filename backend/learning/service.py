"""Application service for Decision Learning lifecycle and API projections."""

from __future__ import annotations

import logging
from datetime import datetime

import database
from behavior.constants import BehaviorInsightStatus, BehaviorInsightType
from behavior.repository import BehaviorRepository
from learning.evidence import build_learning_evidence
from learning.engine import build_learning_recommendations
from learning.models import (
    LearningAcceptResponse,
    LearningDismissResponse,
    LearningRecommendationSummary,
)
from learning.repository import LearningRepository, recommendation_key
from memory.repository import MemoryRepository
from strategy.repository import StrategyRepository

logger = logging.getLogger(__name__)


class LearningService:
    def __init__(
        self,
        *,
        repository: LearningRepository | None = None,
        strategy_repository: StrategyRepository | None = None,
        memory_repository: MemoryRepository | None = None,
        behavior_repository: BehaviorRepository | None = None,
    ) -> None:
        self._repository = repository or LearningRepository()
        self._strategy_repository = strategy_repository or StrategyRepository()
        self._memory_repository = memory_repository or MemoryRepository()
        self._behavior_repository = behavior_repository or BehaviorRepository()

    async def _behavior_blocks_familiar_recommendation(self, user_id: int) -> bool:
        records = await self._behavior_repository.list_by_status(
            user_id,
            [
                BehaviorInsightStatus.CANDIDATE.value,
                BehaviorInsightStatus.CONFIRMED.value,
                BehaviorInsightStatus.SNOOZED.value,
            ],
        )
        return any(
            record.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE.value
            for record in records
        )

    async def synchronize(
        self, user_id: int, *, now: datetime | None = None
    ) -> None:
        """Materialize deterministic candidates from the latest valid outcome."""
        profile = await database.get_profile(user_id)
        snapshot = await self._repository.latest_outcome_snapshot(user_id)
        if profile is None or snapshot is None:
            return

        strategy_id, outcomes = snapshot
        record = await self._strategy_repository.get_by_id(strategy_id, user_id)
        strategy = self._strategy_repository.restore_weekly_strategy(record)
        events = await self._memory_repository.list_events_for_strategy(
            user_id=user_id,
            strategy_id=strategy_id,
        )
        evidence = build_learning_evidence(events, strategy)
        collection = build_learning_recommendations(outcomes, evidence, profile)
        drafts = list(collection.recommendations)

        if await self._behavior_blocks_familiar_recommendation(user_id):
            drafts = [
                draft
                for draft in drafts
                if draft.recommendation_type
                != "profile_enable_prefer_familiar_meals"
            ]

        active_keys = {
            recommendation_key(draft.recommendation_type) for draft in drafts
        }
        expired_count = await self._repository.expire_unmatched(
            user_id=user_id,
            active_keys=active_keys,
            now=now,
        )
        if expired_count:
            logger.info(
                "learning_recommendation_expired count=%s", expired_count
            )

        for draft in drafts:
            _record, created = await self._repository.create_if_absent(
                user_id=user_id,
                source_strategy_id=strategy_id,
                draft=draft,
                now=now,
            )
            if created:
                logger.info(
                    "learning_recommendation_created recommendation_type=%s "
                    "rule_version=%s",
                    draft.recommendation_type,
                    draft.rule_version,
                )

    async def list_recommendations(
        self, user_id: int
    ) -> LearningRecommendationSummary:
        await self.synchronize(user_id)
        recommendations = await self._repository.list_visible(user_id)
        for item in recommendations:
            logger.info(
                "learning_recommendation_viewed recommendation_type=%s",
                item.recommendation_type,
            )
        return LearningRecommendationSummary(
            candidate_count=sum(
                item.status == "candidate" for item in recommendations
            ),
            accepted_count=sum(
                item.status == "accepted" for item in recommendations
            ),
            recommendations=recommendations,
        )

    async def accept(
        self, user_id: int, recommendation_id: str
    ) -> LearningAcceptResponse:
        record = await self._repository.transition(
            user_id=user_id,
            recommendation_id=recommendation_id,
            target_status="accepted",
        )
        logger.info(
            "learning_recommendation_accepted recommendation_type=%s",
            record.recommendation_type,
        )
        return LearningAcceptResponse(
            recommendation_id=record.recommendation_id,
            status="accepted",
            recommended_profile_patch=record.recommended_profile_patch,
        )

    async def dismiss(
        self, user_id: int, recommendation_id: str
    ) -> LearningDismissResponse:
        record = await self._repository.transition(
            user_id=user_id,
            recommendation_id=recommendation_id,
            target_status="dismissed",
        )
        logger.info(
            "learning_recommendation_dismissed recommendation_type=%s",
            record.recommendation_type,
        )
        return LearningDismissResponse(
            recommendation_id=record.recommendation_id,
            status="dismissed",
        )
