"""Coordinates the Memory Engine: events, idempotency, aggregation, lifecycle."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

import database
from memory.aggregation import (
    aggregate_avoid_ingredient,
    aggregate_prefer_faster,
)
from memory.constants import (
    CONFIDENCE_CONFIRMED,
    ConfirmationSource,
    MAX_TARGET_LENGTH,
    MemoryEventType,
    ReplacementReasonCode,
    SignalStatus,
    SignalType,
    TargetType,
)
from memory.models import PreferenceSignalView
from memory.records import MemoryEventRecord, PreferenceSignalRecord
from memory.repository import MemoryRepository
from shopping.normalization import canonical_ingredient_name, display_ingredient_name

logger = logging.getLogger(__name__)

_NO_EXCLUSION_TOKENS = {"", "нет", "-", "none", "no", "не имею", "отсутствуют"}


@dataclass(frozen=True)
class MemoryRecordResult:
    event_recorded: bool
    signal_updated: bool
    deduplicated: bool = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def profile_exclusion_canonicals(profile: dict[str, object]) -> set[str]:
    """Returns canonical keys excluded via typed constraints or legacy allergies."""
    from dietary_constraints import canonical_constraint_value, constraints_from_profile, parse_legacy_allergies

    canonicals: set[str] = set()
    for constraint in constraints_from_profile(profile):
        if constraint.canonical_value:
            canonicals.add(constraint.canonical_value)
    for legacy_value in parse_legacy_allergies(profile.get("allergies")):
        canonical = canonical_constraint_value(legacy_value)
        if canonical:
            canonicals.add(canonical)
    return canonicals


def parse_profile_exclusions(allergies: object) -> set[str]:
    """Returns canonical ingredient keys explicitly excluded in the profile.

    Deprecated: prefer profile_exclusion_canonicals for full profile checks.
    """
    if not isinstance(allergies, str):
        return set()
    stripped = allergies.strip().lower()
    if stripped in _NO_EXCLUSION_TOKENS:
        return set()

    tokens: set[str] = set()
    for raw in allergies.replace(";", ",").split(","):
        candidate = raw.strip()
        if not candidate or candidate.lower() in _NO_EXCLUSION_TOKENS:
            continue
        tokens.add(canonical_ingredient_name(candidate))
    return tokens


class MemoryService:
    def __init__(self, repository: MemoryRepository | None = None) -> None:
        self._repository = repository or MemoryRepository()

    async def record_meal_replaced(
        self,
        *,
        user_id: int,
        strategy_id: str | None,
        meal_id: str | None,
        recipe_id: str | None,
        reason_code: str | None,
        target_ingredient: str | None,
        event_key: str | None,
        now: datetime | None = None,
    ) -> MemoryRecordResult:
        """Records a meal_replaced event and re-aggregates the affected signal.

        Never raises for aggregation issues that should not block replacement;
        persistence errors propagate so the caller can isolate them.
        """
        now = now or _utc_now()
        resolved_key = (event_key or "").strip() or f"gen:{uuid.uuid4()}"

        canonical: str | None = None
        label: str | None = None
        if (
            target_ingredient
            and reason_code
            in (
                ReplacementReasonCode.DISLIKE_INGREDIENT.value,
                ReplacementReasonCode.INGREDIENT_UNAVAILABLE.value,
            )
        ):
            trimmed = target_ingredient.strip()[:MAX_TARGET_LENGTH]
            if trimmed:
                canonical = canonical_ingredient_name(trimmed)
                label = display_ingredient_name(trimmed)

        target_type = TargetType.INGREDIENT.value if canonical else None

        event = MemoryEventRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            event_type=MemoryEventType.MEAL_REPLACED.value,
            event_key=resolved_key,
            strategy_id=strategy_id,
            meal_id=meal_id,
            recipe_id=recipe_id,
            reason_code=reason_code,
            target_type=target_type,
            target_value=canonical,
            target_label=label,
            metadata_json=None,
            created_at=now.isoformat(),
        )

        inserted = await self._repository.insert_event(event)
        if not inserted:
            logger.info(
                "memory_event_deduplicated user_id=%s reason_code=%s",
                user_id,
                reason_code,
            )
            return MemoryRecordResult(event_recorded=False, signal_updated=False, deduplicated=True)

        logger.info(
            "memory_event_created user_id=%s event_type=%s reason_code=%s has_target=%s",
            user_id,
            MemoryEventType.MEAL_REPLACED.value,
            reason_code,
            bool(canonical),
        )

        signal_updated = False
        if reason_code == ReplacementReasonCode.DISLIKE_INGREDIENT.value and canonical:
            signal_updated = await self._reaggregate_avoid(user_id, canonical, label, now)
        elif reason_code == ReplacementReasonCode.FASTER.value:
            signal_updated = await self._reaggregate_faster(user_id, now)

        return MemoryRecordResult(event_recorded=True, signal_updated=signal_updated)

    async def _reaggregate_avoid(
        self, user_id: int, canonical: str, label: str | None, now: datetime
    ) -> bool:
        events = await self._repository.list_events_for_signal(
            user_id=user_id,
            reason_code=ReplacementReasonCode.DISLIKE_INGREDIENT.value,
            target_value=canonical,
        )
        existing = await self._repository.get_signal(
            user_id=user_id,
            signal_type=SignalType.AVOID_INGREDIENT.value,
            target_value=canonical,
        )

        profile = await database.get_profile(user_id) or {}
        excluded = canonical in profile_exclusion_canonicals(profile)

        draft = aggregate_avoid_ingredient(
            events,
            existing,
            now=now,
            target_value=canonical,
            target_label=label,
            profile_excluded=excluded,
        )
        if draft is None:
            if excluded:
                logger.info(
                    "memory_signal_skipped_profile_exclusion user_id=%s signal_type=%s",
                    user_id,
                    SignalType.AVOID_INGREDIENT.value,
                )
            return False

        await self._repository.upsert_signal(user_id, draft, now.isoformat())
        logger.info(
            "memory_signal_updated user_id=%s signal_type=%s status=%s evidence_count=%s",
            user_id,
            draft.signal_type,
            draft.status,
            draft.evidence_count,
        )
        return True

    async def _reaggregate_faster(self, user_id: int, now: datetime) -> bool:
        events = await self._repository.list_events_for_signal(
            user_id=user_id,
            reason_code=ReplacementReasonCode.FASTER.value,
            target_value=None,
        )
        existing = await self._repository.get_signal(
            user_id=user_id,
            signal_type=SignalType.PREFER_FASTER_MEALS.value,
            target_value="",
        )
        draft = aggregate_prefer_faster(
            events,
            existing,
            now=now,
            target_label="Более быстрые блюда",
        )
        if draft is None:
            return False

        await self._repository.upsert_signal(user_id, draft, now.isoformat())
        logger.info(
            "memory_signal_updated user_id=%s signal_type=%s status=%s evidence_count=%s",
            user_id,
            draft.signal_type,
            draft.status,
            draft.evidence_count,
        )
        return True

    async def list_signals(self, user_id: int) -> list[PreferenceSignalView]:
        records = await self._repository.list_active_signals(user_id)
        return [PreferenceSignalView.from_record(record) for record in records]

    async def get_confirmed_signals(self, user_id: int) -> list[PreferenceSignalRecord]:
        return await self._repository.list_confirmed_signals(user_id)

    async def confirm_signal(self, user_id: int, signal_id: str) -> PreferenceSignalView:
        record = await self._repository.set_status(
            signal_id=signal_id,
            user_id=user_id,
            status=SignalStatus.CONFIRMED.value,
            confidence=CONFIDENCE_CONFIRMED,
            now_iso=_utc_now().isoformat(),
            confirmation_source=ConfirmationSource.USER.value,
        )
        logger.info(
            "memory_signal_confirmed user_id=%s signal_type=%s",
            user_id,
            record.signal_type,
        )
        return PreferenceSignalView.from_record(record)

    async def dismiss_signal(self, user_id: int, signal_id: str) -> PreferenceSignalRecord:
        record = await self._repository.set_status(
            signal_id=signal_id,
            user_id=user_id,
            status=SignalStatus.DISMISSED.value,
            confidence=None,
            now_iso=_utc_now().isoformat(),
        )
        logger.info(
            "memory_signal_dismissed user_id=%s signal_type=%s",
            user_id,
            record.signal_type,
        )
        return record
