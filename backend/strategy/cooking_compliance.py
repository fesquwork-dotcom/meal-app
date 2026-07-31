"""Deterministic cooking-session and leftovers checks against WeeklyStrategy."""

from __future__ import annotations

from dataclasses import dataclass

from menu_models import DayMeal, MenuPlan
from strategy.compliance import ComplianceIssue
from strategy.exceptions import StrategyComplianceError
from strategy.models import WeeklyStrategy


@dataclass(frozen=True)
class MealRef:
    day_index: int
    meal_index: int
    meal: DayMeal


def validate_cooking_contract(
    menu: MenuPlan,
    strategy: WeeklyStrategy,
) -> None:
    """Raises StrategyComplianceError when cooking metadata violates strategy."""
    issues: list[ComplianceIssue] = []
    meal_refs = _collect_meal_refs(menu)

    _check_meal_ids(meal_refs, issues)
    meal_by_id = _index_meals_by_id(meal_refs, issues)
    if issues:
        raise StrategyComplianceError("Menu plan violates cooking contract", issues=issues)

    _check_source_references(meal_refs, meal_by_id, issues)
    _check_cook_days(meal_refs, strategy, issues)
    _check_leftovers(meal_refs, meal_by_id, strategy, issues)

    if issues:
        raise StrategyComplianceError("Menu plan violates cooking contract", issues=issues)


def _collect_meal_refs(menu: MenuPlan) -> list[MealRef]:
    refs: list[MealRef] = []
    for day_index, day in enumerate(menu.days_plan):
        for meal_index, meal in enumerate(day.meals):
            refs.append(MealRef(day_index=day_index, meal_index=meal_index, meal=meal))
    return refs


def _check_meal_ids(meal_refs: list[MealRef], issues: list[ComplianceIssue]) -> None:
    seen_ids: dict[str, str] = {}

    for ref in meal_refs:
        path = f"days_plan[{ref.day_index}].meals[{ref.meal_index}]"
        meal_id = ref.meal.meal_id

        if not meal_id:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_MEAL_ID_MISSING",
                    message="Strategy-aware meal must include meal_id",
                    path=path,
                )
            )
            continue

        if meal_id in seen_ids:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_MEAL_ID_DUPLICATE",
                    message=f"Duplicate meal_id '{meal_id}'",
                    path=path,
                )
            )
        else:
            seen_ids[meal_id] = path


def _index_meals_by_id(
    meal_refs: list[MealRef],
    issues: list[ComplianceIssue],
) -> dict[str, MealRef]:
    meal_by_id: dict[str, MealRef] = {}
    for ref in meal_refs:
        meal_id = ref.meal.meal_id
        if not meal_id:
            continue
        meal_by_id[meal_id] = ref
    return meal_by_id


def _check_source_references(
    meal_refs: list[MealRef],
    meal_by_id: dict[str, MealRef],
    issues: list[ComplianceIssue],
) -> None:
    for ref in meal_refs:
        source_id = ref.meal.source_meal_id
        if not source_id:
            continue

        path = f"days_plan[{ref.day_index}].meals[{ref.meal_index}].source_meal_id"
        meal_id = ref.meal.meal_id

        if meal_id and source_id == meal_id:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_SOURCE_MEAL_SELF_REFERENCE",
                    message=f"Meal '{meal_id}' references itself",
                    path=path,
                )
            )
            continue

        source_ref = meal_by_id.get(source_id)
        if source_ref is None:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_SOURCE_MEAL_NOT_FOUND",
                    message=f"source_meal_id '{source_id}' does not exist",
                    path=path,
                )
            )
            continue

        if source_ref.day_index >= ref.day_index:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_LEFTOVER_SOURCE_NOT_EARLIER",
                    message=(
                        f"source_meal_id '{source_id}' must reference an earlier day "
                        f"than day {ref.day_index + 1}"
                    ),
                    path=path,
                )
            )

        if _has_source_cycle(ref.meal.meal_id, meal_by_id):
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_SOURCE_MEAL_CYCLE",
                    message="Circular source_meal_id references detected",
                    path=path,
                )
            )


def _has_source_cycle(
    start_meal_id: str | None,
    meal_by_id: dict[str, MealRef],
) -> bool:
    if not start_meal_id:
        return False

    visited: set[str] = set()
    current_id: str | None = start_meal_id

    while current_id:
        if current_id in visited:
            return True
        visited.add(current_id)
        ref = meal_by_id.get(current_id)
        if ref is None:
            return False
        current_id = ref.meal.source_meal_id

    return False


def _check_cook_days(
    meal_refs: list[MealRef],
    strategy: WeeklyStrategy,
    issues: list[ComplianceIssue],
) -> None:
    cook_days = set(strategy.cook_days)

    for ref in meal_refs:
        day_num = ref.day_index + 1
        path = f"days_plan[{ref.day_index}].meals[{ref.meal_index}]"
        meal = ref.meal

        if meal.requires_cooking is None:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_MEAL_ID_MISSING",
                    message="Strategy-aware meal must include requires_cooking",
                    path=path,
                )
            )
            continue

        prepared_on_day = meal.prepared_on_day
        if prepared_on_day is None:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_PREPARED_DAY_OUT_OF_RANGE",
                    message="Strategy-aware meal must include prepared_on_day",
                    path=path,
                )
            )
            continue

        if prepared_on_day < 1 or prepared_on_day > strategy.days:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_PREPARED_DAY_OUT_OF_RANGE",
                    message=(
                        f"prepared_on_day {prepared_on_day} is outside period 1..{strategy.days}"
                    ),
                    path=path,
                )
            )

        if prepared_on_day > day_num:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_PREPARED_IN_FUTURE",
                    message=(
                        f"prepared_on_day {prepared_on_day} is after meal day {day_num}"
                    ),
                    path=path,
                )
            )

        if meal.requires_cooking:
            if day_num not in cook_days:
                issues.append(
                    ComplianceIssue(
                        code="STRATEGY_COOKING_OUTSIDE_COOK_DAY",
                        message=(
                            f"Day {day_num} {meal.type} requires new cooking, "
                            f"but day {day_num} is not in cook_days {sorted(cook_days)}"
                        ),
                        path=path,
                    )
                )
            if prepared_on_day != day_num:
                issues.append(
                    ComplianceIssue(
                        code="STRATEGY_PREPARED_DAY_MISMATCH",
                        message=(
                            f"requires_cooking=true on day {day_num} expects "
                            f"prepared_on_day={day_num}, got {prepared_on_day}"
                        ),
                        path=path,
                    )
                )
        elif prepared_on_day not in cook_days and meal.uses_leftovers:
            # Leftover base must come from a cook day; prepared_on_day points to that day.
            if prepared_on_day not in cook_days:
                issues.append(
                    ComplianceIssue(
                        code="STRATEGY_PREPARED_DAY_MISMATCH",
                        message=(
                            f"Leftover prepared_on_day {prepared_on_day} must be a cook day "
                            f"{sorted(cook_days)}"
                        ),
                        path=path,
                    )
                )


def _check_leftovers(
    meal_refs: list[MealRef],
    meal_by_id: dict[str, MealRef],
    strategy: WeeklyStrategy,
    issues: list[ComplianceIssue],
) -> None:
    leftover_links = 0

    for ref in meal_refs:
        meal = ref.meal
        path = f"days_plan[{ref.day_index}].meals[{ref.meal_index}]"

        if not meal.uses_leftovers:
            continue

        leftover_links += 1

        if meal.requires_cooking is not False:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_LEFTOVER_REQUIRES_NEW_COOKING",
                    message="uses_leftovers=true requires requires_cooking=false",
                    path=path,
                )
            )

        if not meal.source_meal_id:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_LEFTOVER_SOURCE_MISSING",
                    message="uses_leftovers=true requires source_meal_id",
                    path=path,
                )
            )
            continue

        source_ref = meal_by_id.get(meal.source_meal_id)
        if source_ref is None:
            continue

        source_prepared = source_ref.meal.prepared_on_day
        if source_prepared is None:
            source_prepared = source_ref.day_index + 1
        if meal.prepared_on_day is not None and meal.prepared_on_day != source_prepared:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_LEFTOVER_PREPARED_DAY_MISMATCH",
                    message=(
                        f"prepared_on_day {meal.prepared_on_day} must match source "
                        f"prepared_on_day {source_prepared}"
                    ),
                    path=path,
                )
            )

    if strategy.leftovers_enabled and strategy.days > 1 and leftover_links == 0:
        non_cook_days = [
            day for day in range(1, strategy.days + 1) if day not in set(strategy.cook_days)
        ]
        if non_cook_days:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_LEFTOVERS_REQUIRED",
                    message=(
                        "leftovers_enabled=true requires at least one uses_leftovers meal "
                        "with a valid earlier source"
                    ),
                    path="days_plan",
                )
            )
