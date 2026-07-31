"""SQLite lifecycle persistence for Decision Learning recommendations."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

import aiosqlite

import database
from decision.outcome import DecisionOutcomeCollection
from learning.engine import build_learning_recommendation
from learning.models import (
    LEARNING_RULE_VERSION,
    LearningRecommendation,
    LearningRecommendationType,
    RecommendedProfilePatch,
)

logger = logging.getLogger(__name__)


class LearningRecommendationNotFoundError(Exception):
    pass


class LearningRecommendationTransitionError(Exception):
    pass


class LearningPersistenceError(Exception):
    pass


def recommendation_key(recommendation_type: str) -> str:
    return f"v{LEARNING_RULE_VERSION}:{recommendation_type}"


def _utc_now_iso(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _row_to_recommendation(
    row: aiosqlite.Row,
) -> LearningRecommendation | None:
    try:
        patch_raw = json.loads(row["profile_patch_json"])
        patch = RecommendedProfilePatch.model_validate(patch_raw)
        return build_learning_recommendation(
            row["recommendation_type"],
            recommendation_id=row["id"],
            decision_key=row["decision_key"],
            confidence=row["confidence"],
            patch=patch,
            status=row["status"],
            created_at=row["created_at"],
        )
    except (ValueError, TypeError, json.JSONDecodeError):
        logger.warning(
            "learning_recommendation_unavailable reason=malformed_state"
        )
        return None


class LearningRepository:
    async def latest_outcome_snapshot(
        self, user_id: int
    ) -> tuple[str, DecisionOutcomeCollection] | None:
        """Return the newest finalized strategy with a valid outcome snapshot."""
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_decision_outcomes_column(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT id, decision_outcomes_json
                FROM weekly_strategies
                WHERE user_id = ?
                  AND status IN ('completed', 'superseded')
                  AND decision_outcomes_json IS NOT NULL
                ORDER BY COALESCE(completed_at, superseded_at, updated_at) DESC,
                         created_at DESC
                LIMIT 10
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        for row in rows:
            outcomes = DecisionOutcomeCollection.from_json(
                row["decision_outcomes_json"]
            )
            if outcomes is not None:
                return row["id"], outcomes
        return None

    async def create_if_absent(
        self,
        *,
        user_id: int,
        source_strategy_id: str,
        draft: LearningRecommendation,
        now: datetime | None = None,
    ) -> tuple[LearningRecommendation, bool]:
        """Create once per user/type/rule version; history blocks duplicates."""
        db_path = database.resolve_database_path()
        now_iso = _utc_now_iso(now)
        durable_id = str(uuid.uuid4())
        key = recommendation_key(draft.recommendation_type)
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_learning_recommendations_table(db)
                cursor = await db.execute(
                    """
                    INSERT OR IGNORE INTO learning_recommendations (
                        id, user_id, recommendation_key, recommendation_type,
                        decision_key, status, confidence, rule_version,
                        source_strategy_id, profile_patch_json,
                        created_at, updated_at, accepted_at, dismissed_at, expired_at
                    ) VALUES (?, ?, ?, ?, ?, 'candidate', ?, ?, ?, ?, ?, ?, NULL, NULL, NULL)
                    """,
                    (
                        durable_id,
                        user_id,
                        key,
                        draft.recommendation_type,
                        draft.decision_key,
                        draft.confidence,
                        LEARNING_RULE_VERSION,
                        source_strategy_id,
                        draft.recommended_profile_patch.model_dump_json(
                            exclude_none=True
                        ),
                        now_iso,
                        now_iso,
                    ),
                )
                created = cursor.rowcount > 0
                await cursor.close()
                await db.commit()
                db.row_factory = aiosqlite.Row
                cursor = await db.execute(
                    """
                    SELECT * FROM learning_recommendations
                    WHERE user_id = ? AND recommendation_key = ?
                    """,
                    (user_id, key),
                )
                row = await cursor.fetchone()
                await cursor.close()
        except aiosqlite.Error as exc:
            raise LearningPersistenceError(
                "Failed to create learning recommendation"
            ) from exc
        recommendation = _row_to_recommendation(row) if row is not None else None
        if recommendation is None:
            raise LearningPersistenceError("Saved learning recommendation is invalid")
        return recommendation, created

    async def list_visible(self, user_id: int) -> list[LearningRecommendation]:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_learning_recommendations_table(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM learning_recommendations
                WHERE user_id = ? AND status IN ('candidate', 'accepted')
                ORDER BY created_at DESC, id ASC
                LIMIT 10
                """,
                (user_id,),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [
            item
            for row in rows
            if (item := _row_to_recommendation(row)) is not None
        ]

    async def get_by_id(
        self, user_id: int, recommendation_id: str
    ) -> LearningRecommendation:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_learning_recommendations_table(db)
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM learning_recommendations
                WHERE id = ? AND user_id = ?
                """,
                (recommendation_id, user_id),
            )
            row = await cursor.fetchone()
            await cursor.close()
        if row is None:
            raise LearningRecommendationNotFoundError(recommendation_id)
        recommendation = _row_to_recommendation(row)
        if recommendation is None:
            raise LearningPersistenceError("Learning recommendation is malformed")
        return recommendation

    async def transition(
        self,
        *,
        user_id: int,
        recommendation_id: str,
        target_status: str,
        now: datetime | None = None,
    ) -> LearningRecommendation:
        if target_status not in {"accepted", "dismissed"}:
            raise ValueError("Unsupported learning transition")
        timestamp_column = (
            "accepted_at" if target_status == "accepted" else "dismissed_at"
        )
        allowed_statuses = (
            ("candidate", "accepted")
            if target_status == "accepted"
            else ("candidate", "accepted", "dismissed")
        )
        placeholders = ", ".join("?" for _ in allowed_statuses)
        db_path = database.resolve_database_path()
        now_iso = _utc_now_iso(now)
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_learning_recommendations_table(db)
                cursor = await db.execute(
                    f"""
                    UPDATE learning_recommendations
                    SET status = ?, {timestamp_column} = COALESCE({timestamp_column}, ?),
                        updated_at = ?
                    WHERE id = ? AND user_id = ? AND status IN ({placeholders})
                    """,
                    (
                        target_status,
                        now_iso,
                        now_iso,
                        recommendation_id,
                        user_id,
                        *allowed_statuses,
                    ),
                )
                changed = cursor.rowcount
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise LearningPersistenceError(
                "Failed to update learning recommendation"
            ) from exc
        if changed == 0:
            existing = await self.get_by_id(user_id, recommendation_id)
            raise LearningRecommendationTransitionError(existing.status)
        return await self.get_by_id(user_id, recommendation_id)

    async def expire_unmatched(
        self,
        *,
        user_id: int,
        active_keys: set[str],
        now: datetime | None = None,
    ) -> int:
        """Expire visible recommendations no longer supported by current state."""
        db_path = database.resolve_database_path()
        now_iso = _utc_now_iso(now)
        query = """
            UPDATE learning_recommendations
            SET status = 'expired', expired_at = ?, updated_at = ?
            WHERE user_id = ? AND status IN ('candidate', 'accepted')
        """
        params: list[object] = [now_iso, now_iso, user_id]
        if active_keys:
            placeholders = ", ".join("?" for _ in active_keys)
            query += f" AND recommendation_key NOT IN ({placeholders})"
            params.extend(sorted(active_keys))
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_learning_recommendations_table(db)
                cursor = await db.execute(query, tuple(params))
                count = cursor.rowcount
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise LearningPersistenceError(
                "Failed to expire learning recommendations"
            ) from exc
        return max(0, count)
