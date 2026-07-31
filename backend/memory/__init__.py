"""Memory Engine foundation: structured feedback events and preference signals.

Sprint 5.13 — deterministic, non-LLM aggregation of user actions into
observable preference signals. StrategyBuilder does NOT consume these yet.
"""

from __future__ import annotations

from memory.constants import (
    EVIDENCE_WINDOW_DAYS,
    ReplacementReasonCode,
    SignalStatus,
    SignalType,
)
from memory.exceptions import MemoryPersistenceError, MemorySignalNotFoundError
from memory.service import MemoryRecordResult, MemoryService

__all__ = [
    "EVIDENCE_WINDOW_DAYS",
    "ReplacementReasonCode",
    "SignalStatus",
    "SignalType",
    "MemoryPersistenceError",
    "MemorySignalNotFoundError",
    "MemoryRecordResult",
    "MemoryService",
]
