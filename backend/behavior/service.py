"""Application service for behavior insight API and evaluation."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import database
from behavior.api_models import (
    BehaviorInsightActionResponse,
    BehaviorInsightResponse,
    BehaviorInsightsListResponse,
    BehaviorRevokeResponse,
)
from behavior.constants import BehaviorInsightStatus, BehaviorSnoozeDuration
from behavior.engine import BehaviorLearningEngine
from behavior.exceptions import (
    BehaviorEvaluationError,
    BehaviorInsightNotFoundError,
    BehaviorServiceUnavailableError,
)
from behavior.lifecycle import (
    behavior_insight_affects_strategy,
    profile_preference_remains_after_revoke,
)
from behavior.models import BehaviorEvaluationResult
from behavior.presentation import present_behavior_insight
from behavior.recommendation import can_apply_recommendation, recommendation_key_for_insight
from behavior.recommendation_models import (
    ApplyBehaviorRecommendationResponse,
    BehaviorRecommendationResponse,
)
from behavior.recommendation_service import BehaviorRecommendationService
from planning_preferences import parse_planning_preferences
from behavior.records import BehaviorInsightRecord
from behavior.repository import BehaviorRepository

logger = logging.getLogger(__name__)

_PUBLIC_STATUSES = frozenset(
    {
        BehaviorInsightStatus.CANDIDATE.value,
        BehaviorInsightStatus.CONFIRMED.value,
    }
)


class BehaviorService:
    """Coordinates evaluation, lifecycle actions, and API projections."""

    def __init__(
        self,
        *,
        engine: BehaviorLearningEngine | None = None,
        repository: BehaviorRepository | None = None,
        recommendation_service: BehaviorRecommendationService | None = None,
    ) -> None:
        self._engine = engine or BehaviorLearningEngine()
        self._repository = repository or BehaviorRepository()
        self._recommendation_service = recommendation_service or BehaviorRecommendationService()

    async def evaluate_user(
        self,
        user_id: int,
        *,
        now: datetime | None = None,
    ) -> BehaviorEvaluationResult:
        return await self._engine.evaluate_user(user_id, now=now)

    async def list_active_insights(
        self,
        user_id: int,
        *,
        now: datetime | None = None,
    ) -> BehaviorInsightsListResponse:
        current = _normalize_now(now)
        try:
            await self._engine.evaluate_user(user_id, now=current)
        except BehaviorEvaluationError:
            logger.warning(
                "behavior_list_evaluation_failed user_id=%s",
                user_id,
                exc_info=True,
            )
            try:
                await self._repository.expire_due_insights(user_id, current)
            except BehaviorEvaluationError:
                logger.warning(
                    "behavior_list_expire_failed user_id=%s",
                    user_id,
                    exc_info=True,
                )

        try:
            records = await self._repository.list_active_insights(user_id)
        except BehaviorEvaluationError as exc:
            raise BehaviorServiceUnavailableError("Behavior repository unavailable") from exc

        ordered = _sort_public_insights(records)
        profile = await database.get_profile(user_id)
        profile_planning = (
            parse_planning_preferences(profile).prefer_familiar_meals if profile else None
        )
        responses = [
            _to_response(record, profile_prefer_familiar_meals=profile_planning)
            for record in ordered
        ]
        candidate_count = sum(
            1 for item in responses if item.status == BehaviorInsightStatus.CANDIDATE
        )
        confirmed_count = sum(
            1 for item in responses if item.status == BehaviorInsightStatus.CONFIRMED
        )
        logger.info(
            "behavior_insights_listed user_id=%s candidate_count=%s confirmed_count=%s",
            user_id,
            candidate_count,
            confirmed_count,
        )
        return BehaviorInsightsListResponse(
            insights=responses,
            candidate_count=candidate_count,
            confirmed_count=confirmed_count,
        )

    async def list_confirmed_insights(self, user_id: int) -> list[BehaviorInsightRecord]:
        """Returns confirmed insights for strategy building (no evaluation side effects)."""
        try:
            records = await self._repository.list_confirmed_insights(user_id)
            logger.info(
                "behavior_confirmed_insights_loaded user_id=%s count=%s",
                user_id,
                len(records),
            )
            return records
        except Exception as exc:
            raise BehaviorServiceUnavailableError(
                "Failed to load confirmed behavior insights"
            ) from exc

    async def confirm_insight(
        self,
        user_id: int,
        insight_id: str,
        *,
        now: datetime | None = None,
    ) -> BehaviorInsightActionResponse:
        current = _normalize_now(now)
        record = await self._repository.confirm(user_id, insight_id, now=current)
        logger.info(
            "behavior_insight_confirmed user_id=%s insight_type=%s",
            user_id,
            record.insight_type,
        )
        return BehaviorInsightActionResponse(insight=_to_response(record))

    async def dismiss_insight(
        self,
        user_id: int,
        insight_id: str,
        *,
        now: datetime | None = None,
    ) -> BehaviorInsightActionResponse:
        current = _normalize_now(now)
        record = await self._repository.dismiss(user_id, insight_id, now=current)
        logger.info(
            "behavior_insight_dismissed user_id=%s insight_type=%s",
            user_id,
            record.insight_type,
        )
        return BehaviorInsightActionResponse(insight=_to_response(record))

    async def snooze_insight(
        self,
        user_id: int,
        insight_id: str,
        *,
        duration: BehaviorSnoozeDuration,
        now: datetime | None = None,
    ) -> BehaviorInsightActionResponse:
        current = _normalize_now(now)
        record = await self._repository.snooze(
            user_id, insight_id, duration=duration, now=current
        )
        logger.info(
            "behavior_insight_snoozed insight_type=%s duration=%s",
            record.insight_type,
            duration.value,
        )
        return BehaviorInsightActionResponse(insight=_to_response(record))

    async def revoke_insight(
        self,
        user_id: int,
        insight_id: str,
        *,
        now: datetime | None = None,
    ) -> BehaviorRevokeResponse:
        current = _normalize_now(now)
        existing = await self._repository.get_by_id(user_id, insight_id)
        if existing is None:
            raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")

        was_confirmed = existing.status == BehaviorInsightStatus.CONFIRMED.value
        strategy_effect = behavior_insight_affects_strategy(existing.insight_type)
        preference_remains = profile_preference_remains_after_revoke(existing)

        record = await self._repository.revoke(user_id, insight_id, now=current)

        strategy_effect_changed = was_confirmed and strategy_effect
        if strategy_effect_changed:
            logger.info(
                "behavior_revoke_strategy_input_changed insight_type=%s",
                record.insight_type,
            )
        if preference_remains:
            logger.info(
                "behavior_revoke_profile_preference_preserved insight_type=%s",
                record.insight_type,
            )
        logger.info(
            "behavior_insight_revoked insight_type=%s strategy_effect_changed=%s",
            record.insight_type,
            strategy_effect_changed,
        )
        return BehaviorRevokeResponse(
            insight=_to_response(record),
            strategy_effect_changed=strategy_effect_changed,
            profile_preference_remains_active=preference_remains,
        )

    async def apply_recommendation(
        self,
        user_id: int,
        insight_id: str,
        *,
        expected_revision: int,
        now: datetime | None = None,
    ) -> ApplyBehaviorRecommendationResponse:
        result = await self._recommendation_service.apply_recommendation(
            user_id=user_id,
            insight_id=insight_id,
            expected_revision=expected_revision,
            now=_normalize_now(now) if now else None,
        )
        return ApplyBehaviorRecommendationResponse(
            status=result.status,  # type: ignore[arg-type]
            profile=result.profile,
            profile_revision=result.profile_revision,
            recommendation_key=result.recommendation_key,
        )


def _normalize_now(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        return current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _sort_public_insights(records: list[BehaviorInsightRecord]) -> list[BehaviorInsightRecord]:
    filtered = [record for record in records if record.status in _PUBLIC_STATUSES]
    filtered.sort(key=lambda record: record.id)
    filtered.sort(key=lambda record: record.updated_at, reverse=True)
    filtered.sort(key=lambda record: -record.confidence)
    filtered.sort(
        key=lambda record: 0
        if record.status == BehaviorInsightStatus.CANDIDATE.value
        else 1
    )
    return filtered


def _to_response(
    record: BehaviorInsightRecord,
    *,
    profile_prefer_familiar_meals: bool | None = None,
) -> BehaviorInsightResponse:
    presentation = present_behavior_insight(record)
    rec_key = recommendation_key_for_insight(record)
    recommendation: BehaviorRecommendationResponse | None = None
    if rec_key is not None and record.status == BehaviorInsightStatus.CONFIRMED.value:
        recommendation = BehaviorRecommendationResponse(
            key=rec_key,
            can_apply=can_apply_recommendation(
                record,
                profile_prefer_familiar_meals=profile_prefer_familiar_meals,
            ),
            applied=bool(record.recommendation_applied_at),
        )
    return BehaviorInsightResponse(
        id=record.id,
        type=record.insight_type,
        status=record.status,
        title=presentation.title,
        description=presentation.description,
        evidence_count=record.evidence_count,
        confidence=round(record.confidence, 2),
        can_confirm=record.status == BehaviorInsightStatus.CANDIDATE.value,
        can_dismiss=record.status
        in (
            BehaviorInsightStatus.CANDIDATE.value,
            BehaviorInsightStatus.OBSERVED.value,
        ),
        can_snooze=record.status == BehaviorInsightStatus.CANDIDATE.value,
        can_revoke=record.status == BehaviorInsightStatus.CONFIRMED.value,
        created_at=record.created_at,
        updated_at=record.updated_at,
        recommendation=recommendation,
        snoozed_until=(
            record.snoozed_until
            if record.status == BehaviorInsightStatus.SNOOZED.value
            else None
        ),
        revoked_at=(
            record.revoked_at if record.status == BehaviorInsightStatus.REVOKED.value else None
        ),
    )
