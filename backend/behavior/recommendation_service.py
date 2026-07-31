"""Atomic application of behavior recommendations into Profile (Sprint 5.27)."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite

import database
from behavior.constants import BehaviorInsightStatus, BehaviorInsightType
from behavior.exceptions import (
    BehaviorInsightNotFoundError,
    BehaviorRecommendationAlreadyAppliedError,
    BehaviorRecommendationFailedError,
    BehaviorRecommendationNotAvailableError,
    BehaviorRecommendationProfileStaleError,
)
from behavior.recommendation import recommendation_key_for_insight
from behavior.records import BehaviorInsightRecord
from planning_preferences import (
    PREFER_FAMILIAR_MEALS_RECOMMENDATION_KEY,
    PlanningPreferences,
    parse_planning_preferences,
    serialize_planning_preferences_json,
)
from profile_validation import normalize_profile_for_persistence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecommendationApplyResult:
    status: str
    profile: dict[str, object]
    profile_revision: int
    recommendation_key: str


def _utc_now_iso(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    return current.replace(microsecond=0).isoformat()


def _insight_from_row(row: aiosqlite.Row) -> BehaviorInsightRecord:
    keys = set(row.keys())
    return BehaviorInsightRecord(
        id=row["id"],
        user_id=row["user_id"],
        insight_key=row["insight_key"],
        insight_type=row["insight_type"],
        target_key=row["target_key"],
        target_label=row["target_label"],
        status=row["status"],
        confidence=row["confidence"],
        evidence_count=row["evidence_count"],
        evidence_window_days=row["evidence_window_days"],
        rule_version=row["rule_version"],
        first_seen_at=row["first_seen_at"],
        last_seen_at=row["last_seen_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        confirmed_at=row["confirmed_at"],
        dismissed_at=row["dismissed_at"],
        expires_at=row["expires_at"],
        recommendation_applied_at=(
            row["recommendation_applied_at"] if "recommendation_applied_at" in keys else None
        ),
        recommendation_key=row["recommendation_key"] if "recommendation_key" in keys else None,
    )


def _validate_eligibility(insight: BehaviorInsightRecord, *, now_iso: str) -> None:
    if insight.status != BehaviorInsightStatus.CONFIRMED.value:
        raise BehaviorRecommendationNotAvailableError(
            f"Recommendation not available for status {insight.status}"
        )
    if insight.insight_type != BehaviorInsightType.HIGH_REPLACEMENT_RATE.value:
        raise BehaviorRecommendationNotAvailableError(
            f"Recommendation not available for type {insight.insight_type}"
        )
    if insight.expires_at and insight.expires_at < now_iso:
        raise BehaviorRecommendationNotAvailableError("Insight has expired")


class BehaviorRecommendationService:
    """Applies server-owned behavior recommendations into Profile atomically."""

    async def apply_recommendation(
        self,
        *,
        user_id: int,
        insight_id: str,
        expected_revision: int,
        now: datetime | None = None,
    ) -> RecommendationApplyResult:
        db_path = database.resolve_database_path()
        now_iso = _utc_now_iso(now)
        recommendation_key = PREFER_FAMILIAR_MEALS_RECOMMENDATION_KEY

        logger.info(
            "behavior_recommendation_attempted user_id=%s insight_type=%s recommendation_key=%s",
            user_id,
            BehaviorInsightType.HIGH_REPLACEMENT_RATE.value,
            recommendation_key,
        )

        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_planning_preferences_column(db)
                await database._ensure_behavior_recommendation_columns(db)
                await database._ensure_revision_column(db)
                db.row_factory = aiosqlite.Row
                await db.execute("BEGIN IMMEDIATE")

                cursor = await db.execute(
                    "SELECT * FROM behavior_insights WHERE id = ? AND user_id = ?",
                    (insight_id, user_id),
                )
                row = await cursor.fetchone()
                await cursor.close()
                if row is None:
                    await db.rollback()
                    raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")

                insight = _insight_from_row(row)

                if insight.recommendation_applied_at:
                    profile_row = await database._fetch_profile_row(db, user_id)
                    if profile_row is None:
                        await db.rollback()
                        raise BehaviorRecommendationFailedError("Profile missing")
                    await db.rollback()
                    logger.info("behavior_recommendation_already_applied recommendation_key=%s", recommendation_key)
                    normalized = normalize_profile_for_persistence(profile_row)
                    api_profile = {k: v for k, v in normalized.items() if k != "revision"}
                    return RecommendationApplyResult(
                        status="already_applied",
                        profile=api_profile,
                        profile_revision=int(profile_row.get("revision", 1)),
                        recommendation_key=recommendation_key,
                    )

                try:
                    _validate_eligibility(insight, now_iso=now_iso)
                except BehaviorRecommendationNotAvailableError:
                    await db.rollback()
                    raise

                profile_row = await database._fetch_profile_row(db, user_id)
                if profile_row is None:
                    await db.rollback()
                    raise BehaviorRecommendationFailedError("Profile is required")

                current_revision = int(profile_row.get("revision", 1))
                if current_revision != expected_revision:
                    await db.rollback()
                    logger.info("behavior_recommendation_stale recommendation_key=%s", recommendation_key)
                    raise BehaviorRecommendationProfileStaleError(
                        "Profile revision is stale",
                        current_revision=current_revision,
                    )

                planning = parse_planning_preferences(profile_row)
                result_status: str

                if planning.prefer_familiar_meals is True:
                    result_status = "already_covered"
                    profile_changed = False
                    new_planning = planning
                else:
                    result_status = "applied"
                    profile_changed = True
                    new_planning = PlanningPreferences(prefer_familiar_meals=True)

                new_revision = current_revision
                if profile_changed:
                    planning_json = serialize_planning_preferences_json(new_planning)
                    cursor = await db.execute(
                        """
                        UPDATE profiles
                        SET planning_preferences_json = ?,
                            updated_at = CURRENT_TIMESTAMP,
                            revision = revision + 1
                        WHERE user_id = ? AND revision = ?
                        """,
                        (planning_json, user_id, expected_revision),
                    )
                    if cursor.rowcount != 1:
                        await db.rollback()
                        raise BehaviorRecommendationProfileStaleError(
                            "Profile revision is stale",
                            current_revision=current_revision,
                        )
                    await cursor.close()
                    new_revision = current_revision + 1
                else:
                    logger.info(
                        "behavior_recommendation_already_covered recommendation_key=%s",
                        recommendation_key,
                    )

                cursor = await db.execute(
                    """
                    UPDATE behavior_insights
                    SET recommendation_applied_at = ?,
                        recommendation_key = ?,
                        updated_at = ?
                    WHERE id = ? AND user_id = ? AND recommendation_applied_at IS NULL
                    """,
                    (now_iso, recommendation_key, now_iso, insight_id, user_id),
                )
                if cursor.rowcount != 1:
                    await db.rollback()
                    raise BehaviorRecommendationFailedError("Failed to mark recommendation applied")
                await cursor.close()

                await db.commit()

                saved = await database._fetch_profile_row(db, user_id)
                if saved is None:
                    raise BehaviorRecommendationFailedError("Profile missing after apply")

                normalized = normalize_profile_for_persistence(saved)
                api_profile = {k: v for k, v in normalized.items() if k != "revision"}

                if result_status == "applied":
                    logger.info(
                        "behavior_recommendation_applied recommendation_key=%s revision_from=%s revision_to=%s",
                        recommendation_key,
                        current_revision,
                        new_revision,
                    )
                    logger.info("planning_preference_applied recommendation_key=%s", recommendation_key)

                return RecommendationApplyResult(
                    status=result_status,
                    profile=api_profile,
                    profile_revision=new_revision,
                    recommendation_key=recommendation_key,
                )
        except (
            BehaviorInsightNotFoundError,
            BehaviorRecommendationNotAvailableError,
            BehaviorRecommendationAlreadyAppliedError,
            BehaviorRecommendationProfileStaleError,
        ):
            raise
        except aiosqlite.Error as exc:
            logger.warning("behavior_recommendation_failed error_type=%s", type(exc).__name__)
            raise BehaviorRecommendationFailedError("Recommendation transaction failed") from exc


def serialize_planning_preferences_json(preferences: PlanningPreferences) -> str:
    return json.dumps(
        {"prefer_familiar_meals": preferences.prefer_familiar_meals},
        ensure_ascii=False,
    )
