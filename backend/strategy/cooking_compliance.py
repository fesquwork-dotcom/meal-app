"""Deterministic cooking-session and leftovers checks against WeeklyStrategy."""

from __future__ import annotations

from dataclasses import dataclass

from menu_models import DayMeal, MenuPlan
from strategy.compliance import ComplianceIssue
from strategy.exceptions import StrategyComplianceError
from strategy.models import WeeklyStrategy

EXTRA_COOK_DAY_REQUIRED = "EXTRA_COOK_DAY_REQUIRED"


@dataclass(frozen=True)
class MealRef:
    day_index: int
    meal_index: int
    meal: DayMeal


def validate_cooking_contract(
    menu: MenuPlan,
    strategy: WeeklyStrategy,
    *,
    max_extra_cook_days: int = 0,
) -> list[ComplianceIssue]:
    """Validate cooking metadata against strategy.

    Raises StrategyComplianceError for hard violations.
    Returns soft warnings (e.g. EXTRA_COOK_DAY_REQUIRED) when cooking outside
    preferred cook_days is within ``max_extra_cook_days``.
    """
    issues: list[ComplianceIssue] = []
    warnings: list[ComplianceIssue] = []
    meal_refs = _collect_meal_refs(menu)

    _check_meal_ids(meal_refs, issues)
    meal_by_id = _index_meals_by_id(meal_refs, issues)
    if issues:
        raise StrategyComplianceError("Menu plan violates cooking contract", issues=issues)

    _check_source_references(meal_refs, meal_by_id, issues)
    _check_cook_days(
        meal_refs,
        strategy,
        issues,
        warnings,
        max_extra_cook_days=max_extra_cook_days,
    )
    preferred_and_extra = set(strategy.cook_days) | _actual_cook_days(meal_refs)
    _check_leftovers(meal_refs, meal_by_id, strategy, issues, preferred_and_extra)

    if issues:
        raise StrategyComplianceError("Menu plan violates cooking contract", issues=issues)
    return warnings


def _actual_cook_days(meal_refs: list[MealRef]) -> set[int]:
    return {
        ref.day_index + 1
        for ref in meal_refs
        if ref.meal.requires_cooking
    }


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
    warnings: list[ComplianceIssue],
    *,
    max_extra_cook_days: int,
) -> None:
    preferred = set(strategy.cook_days)
    actual_cook = _actual_cook_days(meal_refs)
    extra = sorted(actual_cook - preferred)

    if len(extra) > max_extra_cook_days:
        for day_num in extra:
            for ref in meal_refs:
                if ref.day_index + 1 != day_num:
                    continue
                meal = ref.meal
                if not meal.requires_cooking:
                    continue
                path = f"days_plan[{ref.day_index}].meals[{ref.meal_index}]"
                issues.append(
                    ComplianceIssue(
                        code="STRATEGY_COOKING_OUTSIDE_COOK_DAY",
                        message=(
                            f"Day {day_num} {meal.type} requires new cooking, "
                            f"but day {day_num} is not in cook_days {sorted(preferred)} "
                            f"(extra cook days {extra} exceed max_extra_cook_days="
                            f"{max_extra_cook_days})"
                        ),
                        path=path,
                    )
                )
    elif extra:
        warnings.append(
            ComplianceIssue(
                code=EXTRA_COOK_DAY_REQUIRED,
                message=(
                    f"Additional cook day(s) {extra} required outside preferred "
                    f"cook_days {sorted(preferred)}; leftovers could not cover all slots"
                ),
                path="days_plan",
            )
        )

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
            # Outside preferred days: already handled as error or EXTRA_COOK_DAY warning.
            if day_num not in preferred and len(extra) > max_extra_cook_days:
                # Already emitted above; skip duplicate prepared_on checks below only.
                pass
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
        elif meal.uses_leftovers:
            # Leftover base must come from a day that actually cooked
            # (preferred cook_days or allowed extra cook day on this menu).
            allowed_prep = preferred | set(extra) if len(extra) <= max_extra_cook_days else preferred
            if prepared_on_day not in allowed_prep:
                issues.append(
                    ComplianceIssue(
                        code="STRATEGY_PREPARED_DAY_MISMATCH",
                        message=(
                            f"Leftover prepared_on_day {prepared_on_day} must be a cook day "
                            f"{sorted(allowed_prep)}"
                        ),
                        path=path,
                    )
                )


def _check_leftovers(
    meal_refs: list[MealRef],
    meal_by_id: dict[str, MealRef],
    strategy: WeeklyStrategy,
    issues: list[ComplianceIssue],
    _allowed_cook_days: set[int],
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
