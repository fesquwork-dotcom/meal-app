"""Deterministic Plan Delta Engine.

Pure function over two parsed plan dicts of the SAME durable plan:
the immutable original snapshot and the current validated revision.
No database, no clock, no LLM — same input, same output.
"""

from __future__ import annotations

from plan_delta.extract import PlanCharacteristics, extract_characteristics
from plan_delta.models import (
    METRIC_UNITS,
    PlanDelta,
    PlanDeltaDirection,
    PlanDeltaMetric,
    PlanDeltaMetricId,
)

# Metric order in the public payload is fixed and deterministic.
_PAIR_METRICS: tuple[tuple[PlanDeltaMetricId, str], ...] = (
    ("total_cost", "total_cost"),
    ("basket_cost", "basket_cost"),
    ("cooking_time_minutes", "cooking_time_minutes"),
    ("cooking_sessions", "cooking_sessions"),
    ("calories", "calories"),
    ("protein_grams", "protein_grams"),
    ("fat_grams", "fat_grams"),
    ("carbs_grams", "carbs_grams"),
)


def _direction(delta: float) -> PlanDeltaDirection:
    if delta > 0:
        return "increased"
    if delta < 0:
        return "decreased"
    return "unchanged"


def _unavailable(metric_id: PlanDeltaMetricId) -> PlanDeltaMetric:
    return PlanDeltaMetric(
        id=metric_id, status="unavailable", unit=METRIC_UNITS[metric_id]
    )


def _pair_metric(
    metric_id: PlanDeltaMetricId,
    original: float | int | None,
    current: float | int | None,
) -> PlanDeltaMetric:
    # Honesty gate: both variants must be computable, otherwise no numbers.
    if original is None or current is None:
        return _unavailable(metric_id)
    delta = round(float(current) - float(original), 2)
    return PlanDeltaMetric(
        id=metric_id,
        status="available",
        unit=METRIC_UNITS[metric_id],
        original=round(float(original), 2),
        current=round(float(current), 2),
        delta=delta,
        direction=_direction(delta),
    )


def _changed_meals_metric(
    original: PlanCharacteristics, current: PlanCharacteristics
) -> PlanDeltaMetric:
    """Meals whose recipe changed in the same (day, meal type) slot.

    Comparable only when both variants expose the same slot structure;
    a structural mismatch means the plans cannot be compared slot by slot.
    """
    if not original.meal_slots or set(original.meal_slots) != set(current.meal_slots):
        return _unavailable("changed_meals")
    changed = sum(
        1
        for slot, original_recipe in original.meal_slots.items()
        if current.meal_slots[slot] != original_recipe
    )
    return PlanDeltaMetric(
        id="changed_meals",
        status="available",
        unit=METRIC_UNITS["changed_meals"],
        original=None,
        current=None,
        delta=float(changed),
        direction="increased" if changed > 0 else "unchanged",
    )


def build_plan_delta(
    original_plan: dict[str, object], current_plan: dict[str, object]
) -> PlanDelta:
    original = extract_characteristics(original_plan)
    current = extract_characteristics(current_plan)

    metrics: list[PlanDeltaMetric] = [
        _pair_metric(
            metric_id,
            getattr(original, attribute),
            getattr(current, attribute),
        )
        for metric_id, attribute in _PAIR_METRICS
    ]
    metrics.insert(2, _changed_meals_metric(original, current))
    return PlanDelta(metrics=metrics)
