"""Plan Delta Engine (Sprint 7.4).

Computes factual, aggregate-only differences between the immutable original
MenuPlan snapshot and the current validated revision. Read-only: never
imported by Decision, Learning, or Strategy layers, never feeds back into
future decisions.
"""

from plan_delta.engine import build_plan_delta
from plan_delta.extract import extract_characteristics
from plan_delta.models import (
    PLAN_DELTA_VERSION,
    PlanDelta,
    PlanDeltaMetric,
)
from plan_delta.service import PlanDeltaService

__all__ = [
    "PLAN_DELTA_VERSION",
    "PlanDelta",
    "PlanDeltaMetric",
    "PlanDeltaService",
    "build_plan_delta",
    "extract_characteristics",
]
