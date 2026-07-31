"""API-facing models for the Memory Engine (user-safe projections)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from memory.records import PreferenceSignalRecord


class PreferenceSignalView(BaseModel):
    """User-safe projection of a preference signal.

    Deliberately excludes raw events, internal timestamps beyond what the UI
    needs, and any free text. Confidence is exposed for the client but is not a
    scientific probability.
    """

    model_config = ConfigDict(extra="forbid")

    id: str
    type: str
    label: str
    status: str
    evidence_count: int
    confidence: float

    @classmethod
    def from_record(cls, record: PreferenceSignalRecord) -> "PreferenceSignalView":
        return cls(
            id=record.id,
            type=record.signal_type,
            label=record.target_label or "",
            status=record.status,
            evidence_count=record.evidence_count,
            confidence=round(record.confidence, 2),
        )
