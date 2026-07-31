"""Explicit positive outcome events (Sprint 6.5).

These events are durable evidence of success — "cooked", "meal suited",
"shopping done", "plan completed". They are recorded idempotently and are
never aggregated into preference signals, never passed to Claude, and never
read by the Decision Engine. Only the retrospective Outcome layer consumes
them.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from memory.constants import (
    MAX_MEAL_ID_LENGTH,
    MEAL_SCOPED_POSITIVE_EVENT_TYPES,
    POSITIVE_EVENT_TYPES,
)
from memory.records import MemoryEventRecord
from memory.repository import MemoryRepository
from strategy.records import StrategyStatus
from strategy.repository import StrategyRepository

logger = logging.getLogger(__name__)

# Events are accepted while the plan is in use and shortly after it ends.
# Superseded strategies are already replaced, so late marks are rejected.
RECORDABLE_STRATEGY_STATUSES: frozenset[str] = frozenset(
    {StrategyStatus.ACTIVE.value, StrategyStatus.COMPLETED.value}
)


class PositiveEventValidationError(ValueError):
    """Raised when a positive event payload violates the contract."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PositiveEventNotAllowedError(Exception):
    """Raised when the strategy state does not accept new positive events."""

    def __init__(self, status: str) -> None:
        super().__init__(f"Positive events are not accepted for status {status}")
        self.status = status


@dataclass(frozen=True)
class PositiveEventResult:
    recorded: bool
    deduplicated: bool


@dataclass(frozen=True)
class PositiveEventUndoResult:
    removed: bool
    absent: bool


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def build_positive_event_key(
    strategy_id: str, event_type: str, meal_id: str | None
) -> str:
    """Server-derived deterministic key: one mark per meal or per strategy."""
    if meal_id:
        return f"positive:{strategy_id}:{event_type}:{meal_id}"
    return f"positive:{strategy_id}:{event_type}"


class PositiveEventService:
    def __init__(
        self,
        memory_repository: MemoryRepository | None = None,
        strategy_repository: StrategyRepository | None = None,
    ) -> None:
        self._memory_repository = memory_repository or MemoryRepository()
        self._strategy_repository = strategy_repository or StrategyRepository()

    @staticmethod
    def _normalize_event_scope(event_type: str, meal_id: str | None) -> str:
        if event_type not in POSITIVE_EVENT_TYPES:
            raise PositiveEventValidationError(
                "POSITIVE_EVENT_TYPE_INVALID", "Unsupported positive event type"
            )

        normalized_meal_id = (meal_id or "").strip()
        if event_type in MEAL_SCOPED_POSITIVE_EVENT_TYPES:
            if not normalized_meal_id:
                raise PositiveEventValidationError(
                    "POSITIVE_EVENT_MEAL_REQUIRED",
                    "Meal-scoped positive events require meal_id",
                )
            if len(normalized_meal_id) > MAX_MEAL_ID_LENGTH:
                raise PositiveEventValidationError(
                    "POSITIVE_EVENT_MEAL_ID_TOO_LONG", "meal_id is too long"
                )
        else:
            # Strategy-scoped events never carry a meal reference.
            normalized_meal_id = ""
        return normalized_meal_id

    async def _require_recordable_strategy(
        self, strategy_id: str, user_id: int, event_type: str
    ) -> None:
        record = await self._strategy_repository.get_by_id(strategy_id, user_id)
        if record.status not in RECORDABLE_STRATEGY_STATUSES:
            logger.info(
                "positive_event_rejected event_type=%s reason=strategy_status status=%s",
                event_type,
                record.status,
            )
            raise PositiveEventNotAllowedError(record.status)

    async def record_positive_event(
        self,
        *,
        user_id: int,
        strategy_id: str,
        event_type: str,
        meal_id: str | None = None,
        now: datetime | None = None,
    ) -> PositiveEventResult:
        """Validates and idempotently records one explicit positive event."""
        normalized_meal_id = self._normalize_event_scope(event_type, meal_id)
        await self._require_recordable_strategy(strategy_id, user_id, event_type)

        now = now or _utc_now()
        event = MemoryEventRecord(
            id=str(uuid.uuid4()),
            user_id=user_id,
            event_type=event_type,
            event_key=build_positive_event_key(
                strategy_id, event_type, normalized_meal_id or None
            ),
            strategy_id=strategy_id,
            meal_id=normalized_meal_id or None,
            recipe_id=None,
            reason_code=None,
            target_type=None,
            target_value=None,
            target_label=None,
            metadata_json=None,
            created_at=now.isoformat(),
        )

        inserted = await self._memory_repository.insert_event(event)
        if inserted:
            logger.info("positive_event_recorded event_type=%s", event_type)
        else:
            logger.info("positive_event_deduplicated event_type=%s", event_type)
        return PositiveEventResult(recorded=inserted, deduplicated=not inserted)

    async def undo_positive_event(
        self,
        *,
        user_id: int,
        strategy_id: str,
        event_type: str,
        meal_id: str | None = None,
    ) -> PositiveEventUndoResult:
        """Removes one explicit mark; repeated undo is harmless."""
        normalized_meal_id = self._normalize_event_scope(event_type, meal_id)
        await self._require_recordable_strategy(strategy_id, user_id, event_type)
        removed = await self._memory_repository.delete_event_by_key(
            user_id=user_id,
            event_key=build_positive_event_key(
                strategy_id, event_type, normalized_meal_id or None
            ),
        )
        logger.info(
            "positive_event_undone event_type=%s removed=%s",
            event_type,
            removed,
        )
        return PositiveEventUndoResult(removed=removed, absent=not removed)
