"""Controlled cook-day relaxation (Sprint 10.11.2).

Strict pass uses allow_cook_day_miss=False. A second pass with
allow_cook_day_miss=True is opened only for COOK_DAY_CONFLICT failures
where hard filters left candidates.
"""

from __future__ import annotations

from typing import Any

from menu_models import MenuPlan
from recipes.planning.diagnostics import PlannerDiagnostics
from recipes.planning.models import PlanStatus, WeeklyRecipePlan
from recipes.planning.weights import WeeklyPlannerConfig
from strategy.cooking_compliance import EXTRA_COOK_DAY_REQUIRED
from strategy.models import WeeklyStrategy

EXTRA_COOK_DAY_EXPLANATION_RU = (
    "Дополнительный день готовки потребовался, потому что leftovers "
    "не закрыли все слоты."
)

__all__ = [
    "EXTRA_COOK_DAY_EXPLANATION_RU",
    "EXTRA_COOK_DAY_REQUIRED",
    "RELAXED_EXTRA_COOK_DAY_PENALTY",
    "build_relaxation_metadata",
    "compute_extra_cook_days",
    "compute_extra_cook_days_from_plan",
    "relaxed_planner_config",
    "should_attempt_cook_day_relaxation",
    "strict_planner_config",
]

# Strong soft penalty for cooking outside preferred cook days (weights unchanged).
RELAXED_EXTRA_COOK_DAY_PENALTY = 0.30

_COOK_DAY_REMOVAL_CODES = frozenset({"COOK_DAY_CONFLICT", "COOK_DAY_REQUIRED"})


def strict_planner_config() -> WeeklyPlannerConfig:
    return WeeklyPlannerConfig(allow_cook_day_miss=False, max_extra_cook_days=1)


def relaxed_planner_config() -> WeeklyPlannerConfig:
    return WeeklyPlannerConfig(
        allow_cook_day_miss=True,
        max_extra_cook_days=1,
        extra_cook_day_penalty=RELAXED_EXTRA_COOK_DAY_PENALTY,
    )


def should_attempt_cook_day_relaxation(plan: WeeklyRecipePlan) -> bool:
    """Gate second planner pass — cook-day conflict only, not time/budget/quality."""
    if plan.status not in {PlanStatus.PARTIAL, PlanStatus.NO_PLAN}:
        return False
    diag = plan.diagnostics
    if str(diag.termination_reason) != "COOK_DAY_CONFLICT":
        return False
    failed_slot = diag.failed_slot
    if not failed_slot:
        return False

    slot = _slot_diag(diag, failed_slot)
    if slot is None:
        return False
    if int(slot.candidate_count_after_hard_filters) <= 0:
        return False

    weekly = dict(slot.weekly_constraint_removals or {})
    if any(int(weekly.get(code, 0)) > 0 for code in _COOK_DAY_REMOVAL_CODES):
        return True

    # Fallback: aggregate constraint stats still show cook-day pressure.
    agg = dict(diag.constraint_statistics or {})
    return any(int(agg.get(code, 0)) > 0 for code in _COOK_DAY_REMOVAL_CODES)


def _slot_diag(diag: PlannerDiagnostics, slot_id: str) -> Any | None:
    for slot in diag.slots or []:
        if getattr(slot, "slot_id", None) == slot_id:
            return slot
    return None


def compute_extra_cook_days(
    menu: MenuPlan,
    strategy: WeeklyStrategy,
) -> list[int]:
    preferred = set(strategy.cook_days)
    actual: set[int] = set()
    for day_index, day in enumerate(menu.days_plan):
        day_num = day_index + 1
        for meal in day.meals:
            if meal.requires_cooking:
                actual.add(day_num)
    return sorted(actual - preferred)


def compute_extra_cook_days_from_plan(
    plan: WeeklyRecipePlan,
    strategy: WeeklyStrategy,
) -> list[int]:
    """Days with true cook-day misses (requires_cooking recipe outside cook_days).

    WeeklyPlannedMeal.requires_cooking is True for every cook *action*, including
    no-cook catalog recipes. Prefer COOK_DAY_MISS planner reason, which is set
    only when recipe.requires_cooking and the slot is outside preferred cook_days.
    """
    preferred = set(strategy.cook_days)
    actual: set[int] = set()
    for meal in plan.meals:
        if meal.is_leftover:
            continue
        if "COOK_DAY_MISS" in (meal.planner_reasons or []):
            actual.add(int(meal.day_index))
    # Defensive: ignore preferred days if reason ever mis-tagged.
    return sorted(actual - preferred)


def build_relaxation_metadata(
    *,
    strict_plan: WeeklyRecipePlan,
    relaxed_plan: WeeklyRecipePlan,
    strategy: WeeklyStrategy,
    relaxation_used: bool,
) -> dict[str, Any]:
    extra = (
        compute_extra_cook_days_from_plan(relaxed_plan, strategy)
        if relaxation_used
        else []
    )
    return {
        "strict_pass_status": strict_plan.status.value,
        "relaxation_used": relaxation_used,
        "extra_cook_days": extra,
        "original_failed_slot": strict_plan.diagnostics.failed_slot,
        "original_diagnostics": strict_plan.diagnostics.to_dict(),
        "relaxed_status": relaxed_plan.status.value if relaxation_used else None,
    }
