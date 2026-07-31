"""Confidence gate for trend metrics.

Every metric must pass this gate. Only ``established`` metrics may expose
quantitative values or percentage changes; everything below stays qualitative.
"""

from __future__ import annotations

from trends.models import TrendConfidence, TrendConfidenceStatus

# Weeks of evidence required to leave each confidence tier.
EMERGING_MIN_WEEKS = 3
ESTABLISHED_MIN_WEEKS = 6


def confidence_status(evidence_weeks: int) -> TrendConfidenceStatus:
    if evidence_weeks >= ESTABLISHED_MIN_WEEKS:
        return "established"
    if evidence_weeks >= EMERGING_MIN_WEEKS:
        return "emerging"
    return "insufficient_data"


def build_confidence(
    *, evidence_weeks: int, completed_strategies: int
) -> TrendConfidence:
    return TrendConfidence(
        status=confidence_status(evidence_weeks),
        weeks=max(0, evidence_weeks),
        completed_strategies=max(0, completed_strategies),
    )
