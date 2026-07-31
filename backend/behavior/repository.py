"""SQLite persistence for behavior insights."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Sequence

import aiosqlite

import database
from behavior.constants import (
    BEHAVIOR_INSIGHT_TTL_DAYS,
    BEHAVIOR_RULES_VERSION,
    CONFIDENCE_CONFIRMED,
    BehaviorInsightStatus,
    BehaviorInsightType,
    BehaviorSnoozeDuration,
)
from behavior.exceptions import (
    BehaviorEvaluationError,
    BehaviorInsightInvalidTransitionError,
    BehaviorInsightNotConfirmableError,
    BehaviorInsightNotDismissibleError,
    BehaviorInsightNotFoundError,
    BehaviorInsightNotRevokableError,
    BehaviorInsightNotSnoozableError,
    BehaviorRevokeFailedError,
    BehaviorServiceUnavailableError,
    BehaviorSnoozeFailedError,
)
from behavior.keys import compute_insight_key, new_insight_id
from behavior.lifecycle import compute_snoozed_until
from behavior.models import BehaviorInsightCandidate
from behavior.records import BehaviorInsightRecord
from memory.records import MemoryEventRecord

logger = logging.getLogger(__name__)

MEAL_REPLACED_EVENT_TYPE = "meal_replaced"


def _utc_now_iso(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    else:
        current = current.astimezone(timezone.utc)
    return current.replace(microsecond=0).isoformat()


def _expires_at_from_last_seen(last_seen_at: str) -> str:
    parsed = datetime.fromisoformat(last_seen_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    expires = parsed + timedelta(days=BEHAVIOR_INSIGHT_TTL_DAYS)
    return expires.replace(microsecond=0).isoformat()


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
        recommendation_key=(
            row["recommendation_key"] if "recommendation_key" in keys else None
        ),
        snoozed_at=row["snoozed_at"] if "snoozed_at" in keys else None,
        snoozed_until=row["snoozed_until"] if "snoozed_until" in keys else None,
        revoked_at=row["revoked_at"] if "revoked_at" in keys else None,
    )


class BehaviorRepository:
    """Persists behavior insights derived from memory events."""

    async def list_meal_replaced_events(
        self,
        user_id: int,
        *,
        since_iso: str,
        limit: int = 500,
    ) -> list[MemoryEventRecord]:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                """
                SELECT * FROM memory_events
                WHERE user_id = ? AND event_type = ? AND created_at >= ?
                ORDER BY created_at ASC
                LIMIT ?
                """,
                (user_id, MEAL_REPLACED_EVENT_TYPE, since_iso, int(limit)),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [
            MemoryEventRecord(
                id=row["id"],
                user_id=row["user_id"],
                event_type=row["event_type"],
                event_key=row["event_key"],
                strategy_id=row["strategy_id"],
                meal_id=row["meal_id"],
                recipe_id=row["recipe_id"],
                reason_code=row["reason_code"],
                target_type=row["target_type"],
                target_value=row["target_value"],
                target_label=row["target_label"],
                metadata_json=row["metadata_json"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def count_strategies_since(self, user_id: int, *, since_iso: str) -> int:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                """
                SELECT COUNT(*) FROM weekly_strategies
                WHERE user_id = ? AND created_at >= ?
                """,
                (user_id, since_iso),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return int(row[0]) if row else 0

    async def get_by_id(self, user_id: int, insight_id: str) -> BehaviorInsightRecord | None:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM behavior_insights WHERE id = ? AND user_id = ?",
                (insight_id, user_id),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _insight_from_row(row) if row is not None else None

    async def get_by_key(self, user_id: int, insight_key: str) -> BehaviorInsightRecord | None:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM behavior_insights WHERE user_id = ? AND insight_key = ?",
                (user_id, insight_key),
            )
            row = await cursor.fetchone()
            await cursor.close()
        return _insight_from_row(row) if row is not None else None

    async def list_by_status(
        self,
        user_id: int,
        statuses: Sequence[str],
    ) -> list[BehaviorInsightRecord]:
        if not statuses:
            return []
        placeholders = ", ".join("?" for _ in statuses)
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                f"""
                SELECT * FROM behavior_insights
                WHERE user_id = ? AND status IN ({placeholders})
                ORDER BY updated_at DESC
                """,
                (user_id, *tuple(statuses)),
            )
            rows = await cursor.fetchall()
            await cursor.close()
        return [_insight_from_row(row) for row in rows]

    async def upsert_insight(
        self,
        user_id: int,
        candidate: BehaviorInsightCandidate,
        *,
        existing: BehaviorInsightRecord | None,
        now: datetime,
    ) -> tuple[BehaviorInsightRecord, bool, bool]:
        """Upsert a candidate. Returns (record, created, updated)."""
        now_iso = _utc_now_iso(now)
        insight_key = compute_insight_key(
            user_id=user_id,
            insight_type=candidate.insight_type,
            target_key=candidate.target_key,
        )
        expires_at = _expires_at_from_last_seen(candidate.last_seen_at)

        if existing is None:
            record = BehaviorInsightRecord(
                id=new_insight_id(),
                user_id=user_id,
                insight_key=insight_key,
                insight_type=candidate.insight_type.value,
                target_key=candidate.target_key,
                target_label=candidate.target_label,
                status=candidate.status.value,
                confidence=candidate.confidence,
                evidence_count=candidate.evidence_count,
                evidence_window_days=candidate.evidence_window_days,
                rule_version=BEHAVIOR_RULES_VERSION,
                first_seen_at=candidate.first_seen_at,
                last_seen_at=candidate.last_seen_at,
                created_at=now_iso,
                updated_at=now_iso,
                confirmed_at=None,
                dismissed_at=None,
                expires_at=expires_at,
            )
            await self._insert(record)
            return record, True, False

        if existing.status == BehaviorInsightStatus.DISMISSED.value:
            return existing, False, False

        if existing.status == BehaviorInsightStatus.REVOKED.value:
            updated = BehaviorInsightRecord(
                id=existing.id,
                user_id=existing.user_id,
                insight_key=existing.insight_key,
                insight_type=existing.insight_type,
                target_key=existing.target_key,
                target_label=existing.target_label,
                status=existing.status,
                confidence=existing.confidence,
                evidence_count=candidate.evidence_count,
                evidence_window_days=candidate.evidence_window_days,
                rule_version=existing.rule_version,
                first_seen_at=existing.first_seen_at,
                last_seen_at=candidate.last_seen_at,
                created_at=existing.created_at,
                updated_at=now_iso,
                confirmed_at=existing.confirmed_at,
                dismissed_at=existing.dismissed_at,
                expires_at=expires_at,
                recommendation_applied_at=existing.recommendation_applied_at,
                recommendation_key=existing.recommendation_key,
                snoozed_at=existing.snoozed_at,
                snoozed_until=existing.snoozed_until,
                revoked_at=existing.revoked_at,
            )
            if _records_equal_for_upsert(existing, updated):
                return existing, False, False
            await self._update(updated)
            return updated, False, True

        if existing.status == BehaviorInsightStatus.SNOOZED.value:
            snooze_active = bool(
                existing.snoozed_until and existing.snoozed_until > now_iso
            )
            if snooze_active:
                updated = BehaviorInsightRecord(
                    id=existing.id,
                    user_id=existing.user_id,
                    insight_key=existing.insight_key,
                    insight_type=existing.insight_type,
                    target_key=existing.target_key,
                    target_label=candidate.target_label or existing.target_label,
                    status=BehaviorInsightStatus.SNOOZED.value,
                    confidence=candidate.confidence,
                    evidence_count=candidate.evidence_count,
                    evidence_window_days=candidate.evidence_window_days,
                    rule_version=existing.rule_version,
                    first_seen_at=existing.first_seen_at,
                    last_seen_at=candidate.last_seen_at,
                    created_at=existing.created_at,
                    updated_at=now_iso,
                    confirmed_at=existing.confirmed_at,
                    dismissed_at=existing.dismissed_at,
                    expires_at=expires_at,
                    recommendation_applied_at=existing.recommendation_applied_at,
                    recommendation_key=existing.recommendation_key,
                    snoozed_at=existing.snoozed_at,
                    snoozed_until=existing.snoozed_until,
                    revoked_at=existing.revoked_at,
                )
                if _records_equal_for_upsert(existing, updated):
                    return existing, False, False
                await self._update(updated)
                logger.info(
                    "behavior_insight_snooze_preserved insight_type=%s",
                    existing.insight_type,
                )
                return updated, False, True

            # Snooze expired — reopen according to current threshold.
            logger.info(
                "behavior_insight_snooze_expired insight_type=%s",
                existing.insight_type,
            )
            updated = BehaviorInsightRecord(
                id=existing.id,
                user_id=existing.user_id,
                insight_key=existing.insight_key,
                insight_type=existing.insight_type,
                target_key=existing.target_key,
                target_label=candidate.target_label or existing.target_label,
                status=candidate.status.value,
                confidence=candidate.confidence,
                evidence_count=candidate.evidence_count,
                evidence_window_days=candidate.evidence_window_days,
                rule_version=existing.rule_version,
                first_seen_at=existing.first_seen_at,
                last_seen_at=candidate.last_seen_at,
                created_at=existing.created_at,
                updated_at=now_iso,
                confirmed_at=existing.confirmed_at,
                dismissed_at=existing.dismissed_at,
                expires_at=expires_at,
                recommendation_applied_at=existing.recommendation_applied_at,
                recommendation_key=existing.recommendation_key,
                snoozed_at=None,
                snoozed_until=None,
                revoked_at=existing.revoked_at,
            )
            await self._update(updated)
            return updated, False, True

        if existing.status == BehaviorInsightStatus.EXPIRED.value:
            updated = BehaviorInsightRecord(
                id=existing.id,
                user_id=existing.user_id,
                insight_key=existing.insight_key,
                insight_type=existing.insight_type,
                target_key=existing.target_key,
                target_label=existing.target_label,
                status=existing.status,
                confidence=existing.confidence,
                evidence_count=candidate.evidence_count,
                evidence_window_days=candidate.evidence_window_days,
                rule_version=existing.rule_version,
                first_seen_at=existing.first_seen_at,
                last_seen_at=candidate.last_seen_at,
                created_at=existing.created_at,
                updated_at=now_iso,
                confirmed_at=existing.confirmed_at,
                dismissed_at=existing.dismissed_at,
                expires_at=expires_at,
                recommendation_applied_at=existing.recommendation_applied_at,
                recommendation_key=existing.recommendation_key,
                snoozed_at=existing.snoozed_at,
                snoozed_until=existing.snoozed_until,
                revoked_at=existing.revoked_at,
            )
            if _records_equal_for_upsert(existing, updated):
                return existing, False, False
            await self._update(updated)
            return updated, False, True

        if existing.status == BehaviorInsightStatus.CONFIRMED.value:
            updated = BehaviorInsightRecord(
                id=existing.id,
                user_id=existing.user_id,
                insight_key=existing.insight_key,
                insight_type=existing.insight_type,
                target_key=existing.target_key,
                target_label=existing.target_label,
                status=existing.status,
                confidence=existing.confidence,
                evidence_count=candidate.evidence_count,
                evidence_window_days=candidate.evidence_window_days,
                rule_version=existing.rule_version,
                first_seen_at=existing.first_seen_at,
                last_seen_at=candidate.last_seen_at,
                created_at=existing.created_at,
                updated_at=now_iso,
                confirmed_at=existing.confirmed_at,
                dismissed_at=existing.dismissed_at,
                expires_at=expires_at,
                recommendation_applied_at=existing.recommendation_applied_at,
                recommendation_key=existing.recommendation_key,
                snoozed_at=existing.snoozed_at,
                snoozed_until=existing.snoozed_until,
                revoked_at=existing.revoked_at,
            )
            if _records_equal_for_upsert(existing, updated):
                return existing, False, False
            await self._update(updated)
            return updated, False, True

        new_status = candidate.status.value
        if existing.status == BehaviorInsightStatus.OBSERVED.value:
            new_status = candidate.status.value

        updated = BehaviorInsightRecord(
            id=existing.id,
            user_id=existing.user_id,
            insight_key=existing.insight_key,
            insight_type=existing.insight_type,
            target_key=existing.target_key,
            target_label=candidate.target_label or existing.target_label,
            status=new_status,
            confidence=candidate.confidence,
            evidence_count=candidate.evidence_count,
            evidence_window_days=candidate.evidence_window_days,
            rule_version=existing.rule_version,
            first_seen_at=existing.first_seen_at,
            last_seen_at=candidate.last_seen_at,
            created_at=existing.created_at,
            updated_at=now_iso,
            confirmed_at=existing.confirmed_at,
            dismissed_at=existing.dismissed_at,
            expires_at=expires_at,
            recommendation_applied_at=existing.recommendation_applied_at,
            recommendation_key=existing.recommendation_key,
            snoozed_at=None,
            snoozed_until=None,
            revoked_at=existing.revoked_at,
        )
        if _records_equal_for_upsert(existing, updated):
            return existing, False, False
        await self._update(updated)
        return updated, False, True

    async def list_active_insights(self, user_id: int) -> list[BehaviorInsightRecord]:
        return await self.list_by_status(
            user_id,
            [
                BehaviorInsightStatus.CANDIDATE.value,
                BehaviorInsightStatus.CONFIRMED.value,
            ],
        )

    async def list_confirmed_insights(self, user_id: int) -> list[BehaviorInsightRecord]:
        return await self.list_by_status(user_id, [BehaviorInsightStatus.CONFIRMED.value])

    async def confirm(self, user_id: int, insight_id: str, *, now: datetime) -> BehaviorInsightRecord:
        existing = await self.get_by_id(user_id, insight_id)
        if existing is None:
            raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
        if existing.status == BehaviorInsightStatus.CONFIRMED.value:
            return existing
        if existing.status != BehaviorInsightStatus.CANDIDATE.value:
            raise BehaviorInsightNotConfirmableError(
                f"Cannot confirm insight in status {existing.status}"
            )

        now_iso = _utc_now_iso(now)
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    """
                    UPDATE behavior_insights
                    SET status = ?, confidence = ?, confirmed_at = ?, updated_at = ?,
                        dismissed_at = NULL
                    WHERE id = ? AND user_id = ? AND status = ?
                    """,
                    (
                        BehaviorInsightStatus.CONFIRMED.value,
                        CONFIDENCE_CONFIRMED,
                        now_iso,
                        now_iso,
                        insight_id,
                        user_id,
                        BehaviorInsightStatus.CANDIDATE.value,
                    ),
                )
                changed = cursor.rowcount
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise BehaviorServiceUnavailableError("Failed to confirm behavior insight") from exc

        if changed == 0:
            refreshed = await self.get_by_id(user_id, insight_id)
            if refreshed is None:
                raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
            if refreshed.status == BehaviorInsightStatus.CONFIRMED.value:
                return refreshed
            raise BehaviorInsightInvalidTransitionError(
                f"Cannot confirm insight in status {refreshed.status}"
            )

        updated = await self.get_by_id(user_id, insight_id)
        if updated is None:
            raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
        return updated

    async def dismiss(self, user_id: int, insight_id: str, *, now: datetime) -> BehaviorInsightRecord:
        existing = await self.get_by_id(user_id, insight_id)
        if existing is None:
            raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
        if existing.status == BehaviorInsightStatus.DISMISSED.value:
            return existing
        if existing.status not in (
            BehaviorInsightStatus.OBSERVED.value,
            BehaviorInsightStatus.CANDIDATE.value,
        ):
            raise BehaviorInsightNotDismissibleError(
                f"Cannot dismiss insight in status {existing.status}"
            )

        now_iso = _utc_now_iso(now)
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    """
                    UPDATE behavior_insights
                    SET status = ?, updated_at = ?, dismissed_at = ?
                    WHERE id = ? AND user_id = ?
                      AND status IN (?, ?)
                    """,
                    (
                        BehaviorInsightStatus.DISMISSED.value,
                        now_iso,
                        now_iso,
                        insight_id,
                        user_id,
                        BehaviorInsightStatus.OBSERVED.value,
                        BehaviorInsightStatus.CANDIDATE.value,
                    ),
                )
                changed = cursor.rowcount
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise BehaviorServiceUnavailableError("Failed to dismiss behavior insight") from exc

        if changed == 0:
            refreshed = await self.get_by_id(user_id, insight_id)
            if refreshed is None:
                raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
            if refreshed.status == BehaviorInsightStatus.DISMISSED.value:
                return refreshed
            raise BehaviorInsightInvalidTransitionError(
                f"Cannot dismiss insight in status {refreshed.status}"
            )

        updated = await self.get_by_id(user_id, insight_id)
        if updated is None:
            raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
        return updated

    async def snooze(
        self,
        user_id: int,
        insight_id: str,
        *,
        duration: BehaviorSnoozeDuration,
        now: datetime,
    ) -> BehaviorInsightRecord:
        existing = await self.get_by_id(user_id, insight_id)
        if existing is None:
            raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")

        until = compute_snoozed_until(now, duration)
        until_iso = until.isoformat()
        now_iso = _utc_now_iso(now)

        if (
            existing.status == BehaviorInsightStatus.SNOOZED.value
            and existing.snoozed_until == until_iso
        ):
            return existing

        if existing.status != BehaviorInsightStatus.CANDIDATE.value:
            raise BehaviorInsightNotSnoozableError(
                f"Cannot snooze insight in status {existing.status}"
            )

        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_behavior_lifecycle_columns(db)
                cursor = await db.execute(
                    """
                    UPDATE behavior_insights
                    SET status = ?,
                        snoozed_at = ?,
                        snoozed_until = ?,
                        updated_at = ?
                    WHERE id = ? AND user_id = ? AND status = ?
                    """,
                    (
                        BehaviorInsightStatus.SNOOZED.value,
                        now_iso,
                        until_iso,
                        now_iso,
                        insight_id,
                        user_id,
                        BehaviorInsightStatus.CANDIDATE.value,
                    ),
                )
                changed = cursor.rowcount
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise BehaviorSnoozeFailedError("Failed to snooze behavior insight") from exc

        if changed == 0:
            refreshed = await self.get_by_id(user_id, insight_id)
            if refreshed is None:
                raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
            if (
                refreshed.status == BehaviorInsightStatus.SNOOZED.value
                and refreshed.snoozed_until == until_iso
            ):
                return refreshed
            logger.info(
                "behavior_transition_conflict transition=snooze insight_type=%s",
                existing.insight_type,
            )
            raise BehaviorInsightNotSnoozableError(
                f"Cannot snooze insight in status {refreshed.status}"
            )

        updated = await self.get_by_id(user_id, insight_id)
        if updated is None:
            raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
        return updated

    async def revoke(
        self,
        user_id: int,
        insight_id: str,
        *,
        now: datetime,
    ) -> BehaviorInsightRecord:
        existing = await self.get_by_id(user_id, insight_id)
        if existing is None:
            raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
        if existing.status == BehaviorInsightStatus.REVOKED.value:
            return existing
        if existing.status != BehaviorInsightStatus.CONFIRMED.value:
            raise BehaviorInsightNotRevokableError(
                f"Cannot revoke insight in status {existing.status}"
            )

        now_iso = _utc_now_iso(now)
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_behavior_lifecycle_columns(db)
                cursor = await db.execute(
                    """
                    UPDATE behavior_insights
                    SET status = ?,
                        revoked_at = ?,
                        updated_at = ?
                    WHERE id = ? AND user_id = ? AND status = ?
                    """,
                    (
                        BehaviorInsightStatus.REVOKED.value,
                        now_iso,
                        now_iso,
                        insight_id,
                        user_id,
                        BehaviorInsightStatus.CONFIRMED.value,
                    ),
                )
                changed = cursor.rowcount
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise BehaviorRevokeFailedError("Failed to revoke behavior insight") from exc

        if changed == 0:
            refreshed = await self.get_by_id(user_id, insight_id)
            if refreshed is None:
                raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
            if refreshed.status == BehaviorInsightStatus.REVOKED.value:
                return refreshed
            logger.info(
                "behavior_transition_conflict transition=revoke insight_type=%s",
                existing.insight_type,
            )
            raise BehaviorInsightNotRevokableError(
                f"Cannot revoke insight in status {refreshed.status}"
            )

        updated = await self.get_by_id(user_id, insight_id)
        if updated is None:
            raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
        return updated

    async def mark_expired(self, user_id: int, insight_id: str, *, now: datetime) -> BehaviorInsightRecord:
        existing = await self.get_by_id(user_id, insight_id)
        if existing is None:
            raise BehaviorInsightNotFoundError(f"Insight {insight_id} not found")
        if existing.status == BehaviorInsightStatus.EXPIRED.value:
            return existing
        if existing.status in (
            BehaviorInsightStatus.CONFIRMED.value,
            BehaviorInsightStatus.DISMISSED.value,
            BehaviorInsightStatus.REVOKED.value,
        ):
            raise BehaviorInsightInvalidTransitionError(
                f"Cannot expire insight in status {existing.status}"
            )
        now_iso = _utc_now_iso(now)
        updated = BehaviorInsightRecord(
            id=existing.id,
            user_id=existing.user_id,
            insight_key=existing.insight_key,
            insight_type=existing.insight_type,
            target_key=existing.target_key,
            target_label=existing.target_label,
            status=BehaviorInsightStatus.EXPIRED.value,
            confidence=existing.confidence,
            evidence_count=existing.evidence_count,
            evidence_window_days=existing.evidence_window_days,
            rule_version=existing.rule_version,
            first_seen_at=existing.first_seen_at,
            last_seen_at=existing.last_seen_at,
            created_at=existing.created_at,
            updated_at=now_iso,
            confirmed_at=existing.confirmed_at,
            dismissed_at=existing.dismissed_at,
            expires_at=existing.expires_at,
            recommendation_applied_at=existing.recommendation_applied_at,
            recommendation_key=existing.recommendation_key,
            snoozed_at=existing.snoozed_at,
            snoozed_until=existing.snoozed_until,
            revoked_at=existing.revoked_at,
        )
        await self._update(updated)
        return updated

    async def expire_due_insights(self, user_id: int, now: datetime) -> int:
        now_iso = _utc_now_iso(now)
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                cursor = await db.execute(
                    """
                    UPDATE behavior_insights
                    SET status = ?, updated_at = ?
                    WHERE user_id = ?
                      AND expires_at IS NOT NULL
                      AND expires_at < ?
                      AND status NOT IN (?, ?, ?, ?)
                    """,
                    (
                        BehaviorInsightStatus.EXPIRED.value,
                        now_iso,
                        user_id,
                        now_iso,
                        BehaviorInsightStatus.CONFIRMED.value,
                        BehaviorInsightStatus.DISMISSED.value,
                        BehaviorInsightStatus.REVOKED.value,
                        BehaviorInsightStatus.EXPIRED.value,
                    ),
                )
                changed = cursor.rowcount
                await cursor.close()
                await db.commit()
        except aiosqlite.Error as exc:
            raise BehaviorEvaluationError("Failed to expire due insights") from exc
        return int(changed)

    async def _insert(self, record: BehaviorInsightRecord) -> None:
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_behavior_recommendation_columns(db)
                await database._ensure_behavior_lifecycle_columns(db)
                await db.execute(
                    """
                    INSERT INTO behavior_insights (
                        id, user_id, insight_key, insight_type, target_key, target_label,
                        status, confidence, evidence_count, evidence_window_days, rule_version,
                        first_seen_at, last_seen_at, created_at, updated_at,
                        confirmed_at, dismissed_at, expires_at,
                        recommendation_applied_at, recommendation_key,
                        snoozed_at, snoozed_until, revoked_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.id,
                        record.user_id,
                        record.insight_key,
                        record.insight_type,
                        record.target_key,
                        record.target_label,
                        record.status,
                        record.confidence,
                        record.evidence_count,
                        record.evidence_window_days,
                        record.rule_version,
                        record.first_seen_at,
                        record.last_seen_at,
                        record.created_at,
                        record.updated_at,
                        record.confirmed_at,
                        record.dismissed_at,
                        record.expires_at,
                        record.recommendation_applied_at,
                        record.recommendation_key,
                        record.snoozed_at,
                        record.snoozed_until,
                        record.revoked_at,
                    ),
                )
                await db.commit()
        except aiosqlite.Error as exc:
            raise BehaviorEvaluationError("Failed to insert behavior insight") from exc

    async def _update(self, record: BehaviorInsightRecord) -> None:
        db_path = database.resolve_database_path()
        try:
            async with aiosqlite.connect(db_path) as db:
                await database._ensure_behavior_lifecycle_columns(db)
                await db.execute(
                    """
                    UPDATE behavior_insights SET
                        insight_type = ?,
                        target_key = ?,
                        target_label = ?,
                        status = ?,
                        confidence = ?,
                        evidence_count = ?,
                        evidence_window_days = ?,
                        rule_version = ?,
                        first_seen_at = ?,
                        last_seen_at = ?,
                        updated_at = ?,
                        confirmed_at = ?,
                        dismissed_at = ?,
                        expires_at = ?,
                        snoozed_at = ?,
                        snoozed_until = ?,
                        revoked_at = ?
                    WHERE id = ? AND user_id = ?
                    """,
                    (
                        record.insight_type,
                        record.target_key,
                        record.target_label,
                        record.status,
                        record.confidence,
                        record.evidence_count,
                        record.evidence_window_days,
                        record.rule_version,
                        record.first_seen_at,
                        record.last_seen_at,
                        record.updated_at,
                        record.confirmed_at,
                        record.dismissed_at,
                        record.expires_at,
                        record.snoozed_at,
                        record.snoozed_until,
                        record.revoked_at,
                        record.id,
                        record.user_id,
                    ),
                )
                await db.commit()
        except aiosqlite.Error as exc:
            raise BehaviorEvaluationError("Failed to update behavior insight") from exc


def _records_equal_for_upsert(
    before: BehaviorInsightRecord,
    after: BehaviorInsightRecord,
) -> bool:
    return (
        before.status == after.status
        and before.confidence == after.confidence
        and before.evidence_count == after.evidence_count
        and before.first_seen_at == after.first_seen_at
        and before.last_seen_at == after.last_seen_at
        and before.expires_at == after.expires_at
        and before.target_label == after.target_label
    )
