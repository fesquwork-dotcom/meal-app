"""Selector Evaluation & Catalog Gap Analysis (Sprint 10.6)."""

from __future__ import annotations

from recipes.evaluation.engine import CatalogEvaluator
from recipes.evaluation.loader import load_evaluation_scenarios
from recipes.evaluation.models import CatalogCoverageReport

__all__ = [
    "CatalogCoverageReport",
    "CatalogEvaluator",
    "load_evaluation_scenarios",
]
