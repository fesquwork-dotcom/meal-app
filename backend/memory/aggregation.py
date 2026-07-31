"""Deterministic aggregation of memory events into preference signals.

Pure functions only: no I/O, no LLM, no wall-clock reads (clock is injected),
and input events are never mutated.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from memory.constants import (
    AVOID_AUTO_CONFIRM_MIN_EVIDENCE,
    CONFIDENCE_CONFIRMED,
    CONFIDENCE_LADDER,
    CONFIDENCE_MAX,
    ConfirmationSource,
    EVIDENCE_WINDOW_DAYS,
    SignalStatus,
    SignalType,
    TargetType,
)
from memory.records import MemoryEventRecord, PreferenceSignalRecord


@dataclass(frozen=True)
class SignalDraft:
    """Computed signal state to be persisted by the service layer."""

    signal_type: str
    target_value: str
    target_label: str | None
    status: str
    confidence: float
    evidence_count: int
    first_observed_at: str
    last_observed_at: str
    confirmation_source: str | None = None


def compute_confidence(evidence_count: int) -> float:
    """Deterministic confidence ladder; not a scientific probability."""
    if evidence_count <= 0:
        return 0.0
    return CONFIDENCE_LADDER.get(evidence_count, CONFIDENCE_MAX)


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts)


def _core(
    *,
    signal_type: str,
    target_value: str,
    target_label: str | None,
    events: list[MemoryEventRecord],
    existing: PreferenceSignalRecord | None,
    now: datetime,
    window_days: int,
    auto_confirm_min: int | None,
    profile_excluded: bool,
) -> SignalDraft | None:
    # Explicit profile exclusion always wins over inferred memory.
    if profile_excluded:
        return None

    cutoff = now - timedelta(days=window_days)
    windowed = [event for event in events if _parse(event.created_at) >= cutoff]

    # Evidence recorded before an explicit dismiss is not resurrected.
    if existing is not None and existing.status == SignalStatus.DISMISSED.value and existing.dismissed_at:
        dismissed_at = _parse(existing.dismissed_at)
        windowed = [event for event in windowed if _parse(event.created_at) > dismissed_at]

    if not windowed:
        return None

    times = sorted(_parse(event.created_at) for event in windowed)
    first_at = times[0]
    last_at = times[-1]
    evidence_count = len(windowed)

    reactivating_dismissed = (
        existing is not None and existing.status == SignalStatus.DISMISSED.value
    )

    # A user-confirmed signal stays confirmed; we only refresh its evidence.
    user_confirmed = (
        existing is not None
        and existing.status == SignalStatus.CONFIRMED.value
        and existing.confidence >= CONFIDENCE_CONFIRMED
    )
    if user_confirmed and not reactivating_dismissed:
        first_observed = _min_iso(existing.first_observed_at, first_at.isoformat())
        existing_source = getattr(existing, "confirmation_source", None)
        return SignalDraft(
            signal_type=signal_type,
            target_value=target_value,
            target_label=target_label or existing.target_label,
            status=SignalStatus.CONFIRMED.value,
            confidence=CONFIDENCE_CONFIRMED,
            evidence_count=evidence_count,
            first_observed_at=first_observed,
            last_observed_at=last_at.isoformat(),
            confirmation_source=existing_source or ConfirmationSource.AUTOMATIC.value,
        )

    confidence = compute_confidence(evidence_count)
    status = SignalStatus.OBSERVED.value
    confirmation_source: str | None = None
    if auto_confirm_min is not None and evidence_count >= auto_confirm_min:
        status = SignalStatus.CONFIRMED.value
        confirmation_source = ConfirmationSource.AUTOMATIC.value

    first_observed = first_at.isoformat()
    if (
        not reactivating_dismissed
        and existing is not None
        and existing.status in (SignalStatus.OBSERVED.value, SignalStatus.CONFIRMED.value)
        and existing.first_observed_at
    ):
        first_observed = _min_iso(existing.first_observed_at, first_observed)

    return SignalDraft(
        signal_type=signal_type,
        target_value=target_value,
        target_label=target_label,
        status=status,
        confidence=confidence,
        evidence_count=evidence_count,
        first_observed_at=first_observed,
        last_observed_at=last_at.isoformat(),
        confirmation_source=confirmation_source,
    )


def _min_iso(left: str | None, right: str) -> str:
    if not left:
        return right
    return left if _parse(left) <= _parse(right) else right


def aggregate_avoid_ingredient(
    events: list[MemoryEventRecord],
    existing: PreferenceSignalRecord | None,
    *,
    now: datetime,
    target_value: str,
    target_label: str | None = None,
    profile_excluded: bool = False,
    window_days: int = EVIDENCE_WINDOW_DAYS,
) -> SignalDraft | None:
    """Aggregates dislike_ingredient events into an avoid_ingredient signal."""
    relevant = [
        event
        for event in events
        if event.target_type == TargetType.INGREDIENT.value
        and event.target_value == target_value
    ]
    return _core(
        signal_type=SignalType.AVOID_INGREDIENT.value,
        target_value=target_value,
        target_label=target_label,
        events=relevant,
        existing=existing,
        now=now,
        window_days=window_days,
        auto_confirm_min=AVOID_AUTO_CONFIRM_MIN_EVIDENCE,
        profile_excluded=profile_excluded,
    )


def aggregate_prefer_faster(
    events: list[MemoryEventRecord],
    existing: PreferenceSignalRecord | None,
    *,
    now: datetime,
    target_label: str | None = None,
    window_days: int = EVIDENCE_WINDOW_DAYS,
) -> SignalDraft | None:
    """Aggregates faster events into a prefer_faster_meals signal (no auto-confirm)."""
    return _core(
        signal_type=SignalType.PREFER_FASTER_MEALS.value,
        target_value="",
        target_label=target_label,
        events=list(events),
        existing=existing,
        now=now,
        window_days=window_days,
        auto_confirm_min=None,
        profile_excluded=False,
    )
