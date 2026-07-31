"""Orchestration service for behavior insight learning."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

from behavior.constants import (
    BEHAVIOR_RULES_VERSION,
    BEHAVIOR_WINDOW_DAYS,
    BehaviorInsightStatus,
)
from behavior.exceptions import BehaviorEvaluationError
from behavior.keys import compute_insight_key
from behavior.models import BehaviorEvaluationResult
from behavior.policy import (
    BehaviorProfileContext,
    ConfirmedMemoryAvoidSignal,
    filter_behavior_candidates,
)
from behavior.repository import BehaviorRepository, _utc_now_iso
from behavior.rules import evaluate_behavior_insights
from memory.constants import SignalType
from memory.repository import MemoryRepository
from memory.service import profile_exclusion_canonicals

logger = logging.getLogger(__name__)


class BehaviorLearningEngine:
    """Loads memory events, evaluates rules, and persists behavior insights."""

    def __init__(
        self,
        *,
        behavior_repository: BehaviorRepository | None = None,
        memory_repository: MemoryRepository | None = None,
    ) -> None:
        self._behavior_repository = behavior_repository or BehaviorRepository()
        self._memory_repository = memory_repository or MemoryRepository()

    async def evaluate_user(
        self,
        user_id: int,
        *,
        now: datetime | None = None,
    ) -> BehaviorEvaluationResult:
        started = time.perf_counter()
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        else:
            current = current.astimezone(timezone.utc)

        logger.info(
            "behavior_evaluation_started user_id=%s rule_version=%s",
            user_id,
            BEHAVIOR_RULES_VERSION,
        )

        try:
            expired_count = await self._behavior_repository.expire_due_insights(
                user_id, current
            )
            if expired_count:
                logger.info(
                    "behavior_insight_expired user_id=%s count=%s rule_version=%s",
                    user_id,
                    expired_count,
                    BEHAVIOR_RULES_VERSION,
                )

            since = current - timedelta(days=BEHAVIOR_WINDOW_DAYS)
            since_iso = _utc_now_iso(since)
            events = await self._behavior_repository.list_meal_replaced_events(
                user_id,
                since_iso=since_iso,
            )
            strategy_count = await self._behavior_repository.count_strategies_since(
                user_id,
                since_iso=since_iso,
            )

            candidates = evaluate_behavior_insights(
                events,
                strategy_count=strategy_count,
                now=current,
            )
            profile_context, memory_avoids = await self._load_policy_context(user_id)
            filtered = filter_behavior_candidates(
                candidates,
                profile_context=profile_context,
                confirmed_memory_signals=memory_avoids,
            )

            created_count = 0
            updated_count = 0
            unchanged_count = 0
            candidate_count = 0
            observed_count = 0

            for candidate in filtered:
                insight_key = compute_insight_key(
                    user_id=user_id,
                    insight_type=candidate.insight_type,
                    target_key=candidate.target_key,
                )
                existing = await self._behavior_repository.get_by_key(
                    user_id, insight_key
                )
                previous_status = existing.status if existing else None
                record, created, updated = await self._behavior_repository.upsert_insight(
                    user_id,
                    candidate,
                    existing=existing,
                    now=current,
                )
                if created:
                    created_count += 1
                    logger.info(
                        "behavior_insight_created user_id=%s insight_type=%s status=%s rule_version=%s",
                        user_id,
                        record.insight_type,
                        record.status,
                        BEHAVIOR_RULES_VERSION,
                    )
                elif updated:
                    updated_count += 1
                    if previous_status != record.status:
                        logger.info(
                            "behavior_insight_status_changed user_id=%s insight_type=%s from_status=%s to_status=%s rule_version=%s",
                            user_id,
                            record.insight_type,
                            previous_status,
                            record.status,
                            BEHAVIOR_RULES_VERSION,
                        )
                else:
                    unchanged_count += 1

                if record.status == BehaviorInsightStatus.CANDIDATE.value:
                    candidate_count += 1
                elif record.status == BehaviorInsightStatus.OBSERVED.value:
                    observed_count += 1

            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "behavior_evaluation_completed user_id=%s rule_version=%s created=%s updated=%s unchanged=%s expired=%s candidate=%s observed=%s duration_ms=%s",
                user_id,
                BEHAVIOR_RULES_VERSION,
                created_count,
                updated_count,
                unchanged_count,
                expired_count,
                candidate_count,
                observed_count,
                duration_ms,
            )
            return BehaviorEvaluationResult(
                created_count=created_count,
                updated_count=updated_count,
                unchanged_count=unchanged_count,
                expired_count=expired_count,
                candidate_count=candidate_count,
                observed_count=observed_count,
            )
        except BehaviorEvaluationError:
            logger.exception(
                "behavior_evaluation_failed user_id=%s rule_version=%s",
                user_id,
                BEHAVIOR_RULES_VERSION,
            )
            raise
        except Exception as exc:
            logger.exception(
                "behavior_evaluation_failed user_id=%s rule_version=%s",
                user_id,
                BEHAVIOR_RULES_VERSION,
            )
            raise BehaviorEvaluationError("Behavior evaluation failed") from exc

    async def _load_policy_context(
        self, user_id: int
    ) -> tuple[BehaviorProfileContext, list[ConfirmedMemoryAvoidSignal]]:
        import database

        profile = await database.get_profile(user_id)
        excluded: set[str] = set()
        if profile:
            excluded = profile_exclusion_canonicals(profile)

        confirmed = await self._memory_repository.list_confirmed_signals(user_id)
        memory_avoids = [
            ConfirmedMemoryAvoidSignal(target_value=signal.target_value)
            for signal in confirmed
            if signal.signal_type == SignalType.AVOID_INGREDIENT.value
        ]
        return BehaviorProfileContext(excluded_canonical_targets=frozenset(excluded)), memory_avoids
