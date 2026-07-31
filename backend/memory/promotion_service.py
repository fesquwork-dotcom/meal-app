"""Atomic promotion of confirmed memory signals into Profile preferences."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import aiosqlite

import database
from cooking_preferences import cooking_preferences_dict, serialize_cooking_preferences_json
from memory.constants import SignalStatus, SignalType
from memory.exceptions import (
    MemoryPromotionFailedError,
    MemoryPromotionProfileStaleError,
    MemorySignalAlreadyPromotedError,
    MemorySignalNotConfirmedError,
    MemorySignalNotFoundError,
    MemorySignalNotPromotableError,
)
from memory.promotion_merge import apply_faster_promotion_merge, apply_promotion_merge
from memory.records import PreferenceSignalRecord
from profile_validation import normalize_profile_for_persistence

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PromotionServiceResult:
    status: str
    profile: dict[str, object]
    profile_revision: int
    constraint_id: str


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _signal_from_row(row: aiosqlite.Row) -> PreferenceSignalRecord:
    keys = set(row.keys())
    return PreferenceSignalRecord(
        id=row["id"],
        user_id=row["user_id"],
        signal_type=row["signal_type"],
        target_value=row["target_value"],
        target_label=row["target_label"],
        status=row["status"],
        confidence=row["confidence"],
        evidence_count=row["evidence_count"],
        first_observed_at=row["first_observed_at"],
        last_observed_at=row["last_observed_at"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        dismissed_at=row["dismissed_at"],
        confirmation_source=row["confirmation_source"] if "confirmation_source" in keys else None,
        promoted_at=row["promoted_at"] if "promoted_at" in keys else None,
        promoted_constraint_id=(
            row["promoted_constraint_id"] if "promoted_constraint_id" in keys else None
        ),
    )


def _validate_eligibility(signal: PreferenceSignalRecord) -> None:
    if signal.promoted_at:
        return
    if signal.signal_type not in (
        SignalType.AVOID_INGREDIENT.value,
        SignalType.PREFER_FASTER_MEALS.value,
    ):
        raise MemorySignalNotPromotableError("Signal type cannot be promoted to profile")
    if signal.status == SignalStatus.OBSERVED.value:
        raise MemorySignalNotConfirmedError("Signal must be confirmed before promotion")
    if signal.status == SignalStatus.DISMISSED.value:
        raise MemorySignalNotPromotableError("Dismissed signals cannot be promoted")
    if signal.status != SignalStatus.CONFIRMED.value:
        raise MemorySignalNotPromotableError("Signal is not eligible for promotion")
    if signal.signal_type == SignalType.AVOID_INGREDIENT.value and not signal.target_value.strip():
        raise MemorySignalNotPromotableError("Signal target is empty")


class MemoryPromotionService:
    """Promotes confirmed avoid signals into profile preferences atomically."""

    async def promote_signal(
        self,
        *,
        user_id: int,
        signal_id: str,
        expected_revision: int,
    ) -> PromotionServiceResult:
        db_path = database.resolve_database_path()
        now_iso = _utc_now_iso()

        try:
            async with aiosqlite.connect(db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL;")
                await database._ensure_promotion_columns(db)
                await database._ensure_dietary_constraints_column(db)
                await database._ensure_cooking_preferences_column(db)
                await database._ensure_revision_column(db)
                db.row_factory = aiosqlite.Row

                await db.execute("BEGIN IMMEDIATE")

                cursor = await db.execute(
                    "SELECT * FROM preference_signals WHERE id = ? AND user_id = ?",
                    (signal_id, user_id),
                )
                row = await cursor.fetchone()
                await cursor.close()
                if row is None:
                    await db.rollback()
                    raise MemorySignalNotFoundError(f"Signal {signal_id} not found")

                signal = _signal_from_row(row)

                if signal.promoted_at and signal.promoted_constraint_id:
                    profile_row = await database._fetch_profile_row(db, user_id)
                    if profile_row is None:
                        await db.rollback()
                        raise MemoryPromotionFailedError("Profile missing for promoted signal")
                    await db.rollback()
                    raise MemorySignalAlreadyPromotedError(
                        "Signal was already promoted",
                        constraint_id=signal.promoted_constraint_id,
                        profile_revision=int(profile_row.get("revision", 1)),
                        profile=profile_row,
                    )

                _validate_eligibility(signal)

                profile_row = await database._fetch_profile_row(db, user_id)
                current_revision = int(profile_row["revision"]) if profile_row else 0
                if current_revision != expected_revision:
                    await db.rollback()
                    raise MemoryPromotionProfileStaleError(
                        "Profile revision is stale",
                        current_revision=current_revision if profile_row else None,
                    )

                if profile_row is None:
                    await db.rollback()
                    raise MemoryPromotionFailedError("Profile is required for promotion")

                if signal.signal_type == SignalType.PREFER_FASTER_MEALS.value:
                    merge = apply_faster_promotion_merge(profile_row)
                else:
                    merge = apply_promotion_merge(
                        profile_row,
                        canonical_target=signal.target_value.strip(),
                        display_label=signal.target_label,
                    )

                result_status = merge.outcome
                updated_profile = dict(profile_row)
                new_revision = current_revision

                if merge.profile_changed:
                    normalized = normalize_profile_for_persistence(
                        {
                            **updated_profile,
                            "dietary_constraints": [
                                item.model_dump(mode="json") for item in merge.constraints
                            ],
                            "allergies": merge.allergies,
                            "cooking_preferences": cooking_preferences_dict(
                                merge.cooking_preferences
                            ),
                        }
                    )
                    meal_types_json = json.dumps(
                        normalized.get("meal_types", []), ensure_ascii=False
                    )
                    proteins_json = json.dumps(
                        normalized.get("proteins", []), ensure_ascii=False
                    )
                    dietary_json = json.dumps(
                        normalized.get("dietary_constraints", []), ensure_ascii=False
                    )
                    cooking_json = serialize_cooking_preferences_json(merge.cooking_preferences)

                    cursor = await db.execute(
                        """
                        UPDATE profiles
                        SET
                            first_name = ?,
                            budget = ?,
                            days = ?,
                            persons = ?,
                            proteins = ?,
                            goal = ?,
                            cooktime = ?,
                            allergies = ?,
                            dietary_constraints_json = ?,
                            cooking_preferences_json = ?,
                            store = ?,
                            meal_types = ?,
                            updated_at = CURRENT_TIMESTAMP,
                            revision = revision + 1
                        WHERE user_id = ? AND revision = ?
                        """,
                        (
                            normalized.get("first_name", ""),
                            normalized.get("budget"),
                            normalized.get("days"),
                            normalized.get("persons"),
                            proteins_json,
                            normalized.get("goal"),
                            normalized.get("cooktime"),
                            normalized.get("allergies"),
                            dietary_json,
                            cooking_json,
                            normalized.get("store"),
                            meal_types_json,
                            user_id,
                            expected_revision,
                        ),
                    )
                    if cursor.rowcount != 1:
                        await cursor.close()
                        current = await database._fetch_profile_row(db, user_id)
                        await db.rollback()
                        raise MemoryPromotionProfileStaleError(
                            "Profile revision changed during promotion",
                            current_revision=int(current["revision"]) if current else None,
                        )
                    await cursor.close()
                    saved = await database._fetch_profile_row(db, user_id)
                    if saved is None:
                        await db.rollback()
                        raise MemoryPromotionFailedError("Profile save failed")
                    updated_profile = saved
                    new_revision = int(saved["revision"])

                cursor = await db.execute(
                    """
                    UPDATE preference_signals
                    SET status = ?, updated_at = ?, dismissed_at = ?,
                        promoted_at = ?, promoted_constraint_id = ?
                    WHERE id = ? AND user_id = ? AND promoted_at IS NULL
                    """,
                    (
                        SignalStatus.DISMISSED.value,
                        now_iso,
                        now_iso,
                        now_iso,
                        merge.constraint_id,
                        signal_id,
                        user_id,
                    ),
                )
                if cursor.rowcount != 1:
                    await cursor.close()
                    await db.rollback()
                    raise MemoryPromotionFailedError("Failed to mark signal as promoted")
                await cursor.close()

                await db.commit()

                if merge.outcome == "promoted":
                    logger.info(
                        "memory_promotion_succeeded user_id=%s signal_type=%s "
                        "constraint_kind=preference revision_from=%s revision_to=%s",
                        user_id,
                        signal.signal_type,
                        expected_revision,
                        new_revision,
                    )
                elif merge.outcome == "already_covered":
                    logger.info(
                        "memory_promotion_already_covered user_id=%s signal_type=%s "
                        "constraint_kind=allergy_or_intolerance",
                        user_id,
                        signal.signal_type,
                    )
                else:
                    logger.info(
                        "memory_promotion_succeeded user_id=%s signal_type=%s "
                        "result=already_promoted",
                        user_id,
                        signal.signal_type,
                    )

                return PromotionServiceResult(
                    status=result_status,
                    profile=updated_profile,
                    profile_revision=new_revision,
                    constraint_id=merge.constraint_id,
                )
        except (
            MemorySignalNotFoundError,
            MemorySignalNotPromotableError,
            MemorySignalNotConfirmedError,
            MemorySignalAlreadyPromotedError,
            MemoryPromotionProfileStaleError,
        ):
            raise
        except Exception as exc:
            logger.exception("promotion_transaction_failed user_id=%s", user_id)
            raise MemoryPromotionFailedError("Promotion transaction failed") from exc
