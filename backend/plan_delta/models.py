"""Domain models for the Plan Delta Engine (Sprint 7.4).

Plan Delta compares two durable states of the same plan — the immutable
original snapshot and the current validated revision — and reports factual,
aggregate-only differences. It never mixes plans from different weeks and
never feeds back into decisions.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

PLAN_DELTA_VERSION = 1

PlanDeltaMetricId = Literal[
    "total_cost",
    "basket_cost",
    "changed_meals",
    "cooking_time_minutes",
    "cooking_sessions",
    "calories",
    "protein_grams",
    "fat_grams",
    "carbs_grams",
]

# Honesty gate: a metric is exposed only when BOTH plan variants carry fully
# parseable data for it; otherwise it is reported as unavailable instead of
# being approximated.
PlanDeltaMetricStatus = Literal["available", "unavailable"]

PlanDeltaDirection = Literal["increased", "decreased", "unchanged"]

PlanDeltaUnit = Literal["rub", "count", "minutes", "kcal", "grams"]

METRIC_UNITS: dict[str, PlanDeltaUnit] = {
    "total_cost": "rub",
    "basket_cost": "rub",
    "changed_meals": "count",
    "cooking_time_minutes": "minutes",
    "cooking_sessions": "count",
    "calories": "kcal",
    "protein_grams": "grams",
    "fat_grams": "grams",
    "carbs_grams": "grams",
}


class PlanDeltaMetric(BaseModel):
    """One factual difference between original and current plan variants."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    id: PlanDeltaMetricId
    status: PlanDeltaMetricStatus
    unit: PlanDeltaUnit
    # Pair metrics carry both variants; count-only metrics (changed_meals)
    # carry only the delta. All None when the metric is unavailable.
    original: float | None = None
    current: float | None = None
    delta: float | None = None
    direction: PlanDeltaDirection | None = None


class PlanDelta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    version: int = PLAN_DELTA_VERSION
    metrics: list[PlanDeltaMetric] = Field(default_factory=list, max_length=12)
