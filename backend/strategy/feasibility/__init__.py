"""Strategy feasibility package (Sprint 10.11.4)."""

from strategy.feasibility.analyzer import StrategyFeasibilityAnalyzer
from strategy.feasibility.models import (
    CatalogGapSignal,
    FeasibilityIssue,
    FeasibilityIssueCode,
    FeasibilityStatus,
    StrategyFeasibilityResult,
    SuggestedAdjustment,
    SuggestionCode,
)

__all__ = [
    "CatalogGapSignal",
    "FeasibilityIssue",
    "FeasibilityIssueCode",
    "FeasibilityStatus",
    "StrategyFeasibilityAnalyzer",
    "StrategyFeasibilityResult",
    "SuggestedAdjustment",
    "SuggestionCode",
]
