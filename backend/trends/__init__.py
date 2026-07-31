"""Read-only Trend Engine (Sprint 7.1).

Observes decision history and explicit user marks to compute long-term
trends. Never imported by the Decision Engine, Learning, or Strategy layers.
"""

from trends.api_models import TrendSummaryResponse
from trends.engine import build_trend_summary
from trends.models import (
    TREND_VERSION,
    TrendConfidence,
    TrendMetric,
    TrendSummary,
)
from trends.summary import TrendService

__all__ = [
    "TREND_VERSION",
    "TrendConfidence",
    "TrendMetric",
    "TrendSummary",
    "TrendSummaryResponse",
    "TrendService",
    "build_trend_summary",
]
