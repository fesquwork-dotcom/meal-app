"""Immutable memory inputs for deterministic strategy building (no I/O)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Sequence

from memory.constants import ConfirmationSource, SignalStatus, SignalType
from memory.records import PreferenceSignalRecord

MEMORY_CONTEXT_VERSION = 1
MAX_MEMORY_AVOIDS_APPLIED = 30


@dataclass(frozen=True)
class ConfirmedMemorySignal:
    signal_id: str
    signal_type: str
    target_value: str
    target_label: str | None
    confirmation_source: str
    updated_at: str = ""


@dataclass(frozen=True)
class StrategyMemoryContext:
    """Confirmed memory signals prepared for StrategyBuilder."""

    avoided_ingredients: tuple[str, ...] = ()
    prefer_faster_meals: bool = False
    signals: tuple[ConfirmedMemorySignal, ...] = ()

    @staticmethod
    def empty() -> "StrategyMemoryContext":
        return StrategyMemoryContext()


@dataclass(frozen=True)
class AppliedMemoryDecision:
    signal_id: str
    signal_type: str
    target_value: str | None
    confirmation_source: str
    applied: bool
    reason_code: str


@dataclass(frozen=True)
class AppliedMemorySnapshot:
    version: int = MEMORY_CONTEXT_VERSION
    avoided_ingredients: tuple[str, ...] = ()
    prefer_faster_meals: bool = False
    decisions: tuple[AppliedMemoryDecision, ...] = ()

    def to_json(self) -> str:
        payload = {
            "version": self.version,
            "avoided_ingredients": list(self.avoided_ingredients),
            "prefer_faster_meals": self.prefer_faster_meals,
            "decisions": [
                {
                    "signal_id": item.signal_id,
                    "signal_type": item.signal_type,
                    "target_value": item.target_value,
                    "confirmation_source": item.confirmation_source,
                    "applied": item.applied,
                    "reason_code": item.reason_code,
                }
                for item in self.decisions
            ],
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str | None) -> "AppliedMemorySnapshot | None":
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(parsed, dict):
            return None

        version = parsed.get("version", 1)
        avoided = parsed.get("avoided_ingredients", [])
        prefer_faster = parsed.get("prefer_faster_meals", False)
        decisions_raw = parsed.get("decisions", [])

        if not isinstance(avoided, list) or not isinstance(prefer_faster, bool):
            return None
        if not isinstance(decisions_raw, list):
            return None

        decisions: list[AppliedMemoryDecision] = []
        for item in decisions_raw:
            if not isinstance(item, dict):
                continue
            signal_id = item.get("signal_id")
            signal_type = item.get("signal_type")
            if not isinstance(signal_id, str) or not isinstance(signal_type, str):
                continue
            decisions.append(
                AppliedMemoryDecision(
                    signal_id=signal_id,
                    signal_type=signal_type,
                    target_value=item.get("target_value")
                    if isinstance(item.get("target_value"), str)
                    else None,
                    confirmation_source=str(item.get("confirmation_source") or "automatic"),
                    applied=bool(item.get("applied")),
                    reason_code=str(item.get("reason_code") or ""),
                )
            )

        return cls(
            version=int(version) if isinstance(version, int) else 1,
            avoided_ingredients=tuple(
                value for value in avoided if isinstance(value, str) and value.strip()
            ),
            prefer_faster_meals=prefer_faster,
            decisions=tuple(decisions),
        )

    @staticmethod
    def empty() -> "AppliedMemorySnapshot":
        return AppliedMemorySnapshot()


def _resolve_confirmation_source(record: PreferenceSignalRecord) -> str:
    source = getattr(record, "confirmation_source", None)
    if source in (ConfirmationSource.USER.value, ConfirmationSource.AUTOMATIC.value):
        return source
    # Legacy confirmed rows without provenance default to automatic.
    return ConfirmationSource.AUTOMATIC.value


def build_strategy_memory_context(
    signals: Sequence[PreferenceSignalRecord],
) -> StrategyMemoryContext:
    """Builds StrategyMemoryContext from confirmed signals only."""
    confirmed = [
        signal
        for signal in signals
        if signal.status == SignalStatus.CONFIRMED.value and not signal.promoted_at
    ]

    avoid_targets: list[str] = []
    avoid_seen: set[str] = set()
    prefer_faster = False
    confirmed_signals: list[ConfirmedMemorySignal] = []

    for signal in sorted(confirmed, key=lambda item: (item.signal_type, item.target_value, item.id)):
        source = _resolve_confirmation_source(signal)
        entry = ConfirmedMemorySignal(
            signal_id=signal.id,
            signal_type=signal.signal_type,
            target_value=signal.target_value,
            target_label=signal.target_label,
            confirmation_source=source,
            updated_at=signal.updated_at,
        )
        confirmed_signals.append(entry)

        if signal.signal_type == SignalType.AVOID_INGREDIENT.value:
            target = signal.target_value.strip()
            if target and target not in avoid_seen:
                avoid_seen.add(target)
                avoid_targets.append(target)
        elif signal.signal_type == SignalType.PREFER_FASTER_MEALS.value:
            prefer_faster = True

    return StrategyMemoryContext(
        avoided_ingredients=tuple(avoid_targets),
        prefer_faster_meals=prefer_faster,
        signals=tuple(confirmed_signals),
    )
