"""Cooking instance ID assignment, graph validation, and basket deduplication keys."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from menu_models import DayMeal, MenuPlan
from menu_validation import ValidationIssue

logger = logging.getLogger(__name__)

COOKING_INSTANCE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
MAX_COOKING_INSTANCES = 200
MAX_MEALS_PER_INSTANCE = 50


def is_valid_cooking_instance_id(instance_id: str | None) -> bool:
    if not instance_id or not isinstance(instance_id, str):
        return False
    stripped = instance_id.strip()
    return bool(stripped and COOKING_INSTANCE_ID_PATTERN.match(stripped))


def sanitize_cooking_instance_id(instance_id: str | None) -> str | None:
    if not instance_id or not isinstance(instance_id, str):
        return None
    stripped = instance_id.strip()
    if is_valid_cooking_instance_id(stripped):
        return stripped
    return None


def default_cooking_instance_id_for_meal(meal: DayMeal) -> str:
    if meal.meal_id:
        return f"cook_{meal.meal_id}"
    return f"cook_{meal.type}_{meal.recipe_name}"


def menu_has_cooking_instances(menu: MenuPlan) -> bool:
    return any(meal.cooking_instance_id for day in menu.days_plan for meal in day.meals)


def _collect_meals_by_id(menu: MenuPlan) -> dict[str, DayMeal]:
    indexed: dict[str, DayMeal] = {}
    for day in menu.days_plan:
        for meal in day.meals:
            if meal.meal_id:
                indexed[meal.meal_id] = meal
    return indexed


@dataclass(frozen=True)
class CookingContributionMeta:
    meal_id: str | None
    recipe_id: str | None
    cooking_instance_id: str | None
    requires_cooking: bool
    uses_leftovers: bool
    source_meal_id: str | None
    prepared_on_day: int | None
    day_index: int


def build_cooking_contribution_meta(menu: MenuPlan) -> list[CookingContributionMeta]:
    meta: list[CookingContributionMeta] = []
    for day_index, day in enumerate(menu.days_plan):
        for meal in day.meals:
            meta.append(
                CookingContributionMeta(
                    meal_id=meal.meal_id,
                    recipe_id=meal.recipe_id,
                    cooking_instance_id=meal.cooking_instance_id,
                    requires_cooking=bool(meal.requires_cooking),
                    uses_leftovers=meal.uses_leftovers,
                    source_meal_id=meal.source_meal_id,
                    prepared_on_day=meal.prepared_on_day,
                    day_index=day_index,
                )
            )
    return meta


def _validate_cooking_graph(
    menu: MenuPlan,
    *,
    strategy_aware: bool,
) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []
    meal_by_id = _collect_meals_by_id(menu)
    instance_prepared_days: dict[str, set[int]] = {}
    instance_meal_counts: dict[str, int] = {}

    for day_index, day in enumerate(menu.days_plan):
        day_num = day_index + 1
        for meal_index, meal in enumerate(day.meals):
            path = f"days_plan[{day_index}].meals[{meal_index}]"
            instance_id = meal.cooking_instance_id

            if strategy_aware and not instance_id:
                errors.append(
                    ValidationIssue(
                        code="COOKING_INSTANCE_ID_MISSING",
                        message="Strategy-aware meal missing cooking_instance_id",
                        path=path,
                        severity="error",
                    )
                )
                continue

            if not instance_id:
                continue

            if not is_valid_cooking_instance_id(instance_id):
                errors.append(
                    ValidationIssue(
                        code="COOKING_INSTANCE_ID_INVALID",
                        message=f"Invalid cooking_instance_id '{instance_id}'",
                        path=path,
                        severity="error",
                    )
                )
                continue

            instance_meal_counts[instance_id] = instance_meal_counts.get(instance_id, 0) + 1
            if instance_meal_counts[instance_id] > MAX_MEALS_PER_INSTANCE:
                errors.append(
                    ValidationIssue(
                        code="COOKING_INSTANCE_INVALID_REUSE",
                        message=f"Too many meals share cooking_instance_id '{instance_id}'",
                        path=path,
                        severity="error",
                    )
                )

            if meal.prepared_on_day is not None:
                instance_prepared_days.setdefault(instance_id, set()).add(meal.prepared_on_day)
                if len(instance_prepared_days[instance_id]) > 1:
                    errors.append(
                        ValidationIssue(
                            code="COOKING_INSTANCE_MULTIPLE_PREPARED_DAYS",
                            message=(
                                f"cooking_instance_id '{instance_id}' has inconsistent "
                                "prepared_on_day values"
                            ),
                            path=path,
                            severity="error",
                        )
                    )

            if meal.uses_leftovers and meal.source_meal_id:
                source_meal = meal_by_id.get(meal.source_meal_id)
                if source_meal is None:
                    errors.append(
                        ValidationIssue(
                            code="COOKING_INSTANCE_SOURCE_MISMATCH",
                            message=f"source_meal_id '{meal.source_meal_id}' not found",
                            path=path,
                            severity="error",
                        )
                    )
                    continue
                source_day = next(
                    (
                        idx
                        for idx, d in enumerate(menu.days_plan)
                        for m in d.meals
                        if m.meal_id == meal.source_meal_id
                    ),
                    day_index,
                )
                if source_day >= day_index:
                    errors.append(
                        ValidationIssue(
                            code="COOKING_INSTANCE_SOURCE_MISMATCH",
                            message="source meal must be on an earlier day",
                            path=path,
                            severity="error",
                        )
                    )
                expected = source_meal.cooking_instance_id
                if expected and instance_id != expected:
                    errors.append(
                        ValidationIssue(
                            code="COOKING_INSTANCE_SOURCE_MISMATCH",
                            message=(
                                f"Leftover meal instance '{instance_id}' does not match "
                                f"source instance '{expected}'"
                            ),
                            path=path,
                            severity="error",
                        )
                    )

            if meal.requires_cooking and meal.prepared_on_day is not None:
                if meal.prepared_on_day != day_num:
                    errors.append(
                        ValidationIssue(
                            code="COOKING_INSTANCE_PREPARED_DAY_MISMATCH",
                            message=(
                                f"requires_cooking meal prepared_on_day {meal.prepared_on_day} "
                                f"does not match day {day_num}"
                            ),
                            path=path,
                            severity="error",
                        )
                    )

    if len(instance_meal_counts) > MAX_COOKING_INSTANCES:
        errors.append(
            ValidationIssue(
                code="COOKING_INSTANCE_INVALID_REUSE",
                message=f"Cooking instance count exceeds limit {MAX_COOKING_INSTANCES}",
                path="days_plan",
                severity="error",
            )
        )

    logger.info(
        "cooking_graph meals=%s instances=%s shared_instances=%s",
        sum(len(day.meals) for day in menu.days_plan),
        len(instance_meal_counts),
        sum(1 for count in instance_meal_counts.values() if count > 1),
    )
    return errors


def assign_and_validate_cooking_instances(
    menu: MenuPlan,
    *,
    strategy_aware: bool,
) -> tuple[MenuPlan, list[ValidationIssue]]:
    """Deterministically assigns cooking instance IDs and returns validation issues."""
    days_plan = [day.model_copy(deep=True) for day in menu.days_plan]

    for day_index, day in enumerate(days_plan):
        for meal_index, meal in enumerate(day.meals):
            sanitized = sanitize_cooking_instance_id(meal.cooking_instance_id)
            if meal.cooking_instance_id and sanitized is None:
                day.meals[meal_index] = meal.model_copy(update={"cooking_instance_id": None})
            elif sanitized and sanitized != meal.cooking_instance_id:
                day.meals[meal_index] = meal.model_copy(update={"cooking_instance_id": sanitized})

    updated = menu.model_copy(update={"days_plan": days_plan})

    for day in updated.days_plan:
        for meal_index, meal in enumerate(day.meals):
            if meal.cooking_instance_id:
                continue
            if meal.requires_cooking:
                day.meals[meal_index] = meal.model_copy(
                    update={"cooking_instance_id": default_cooking_instance_id_for_meal(meal)}
                )

    meal_by_id = _collect_meals_by_id(updated)
    for day in updated.days_plan:
        for meal_index, meal in enumerate(day.meals):
            if meal.cooking_instance_id:
                continue
            if meal.uses_leftovers and meal.source_meal_id:
                source_meal = meal_by_id.get(meal.source_meal_id)
                if source_meal and source_meal.cooking_instance_id:
                    day.meals[meal_index] = meal.model_copy(
                        update={"cooking_instance_id": source_meal.cooking_instance_id}
                    )

    for day in updated.days_plan:
        for meal_index, meal in enumerate(day.meals):
            if meal.cooking_instance_id or not strategy_aware:
                continue
            day.meals[meal_index] = meal.model_copy(
                update={"cooking_instance_id": default_cooking_instance_id_for_meal(meal)}
            )

    issues = _validate_cooking_graph(updated, strategy_aware=strategy_aware)
    return updated, issues


def validate_cooking_instance_graph(
    menu: MenuPlan,
    *,
    strategy_aware: bool,
) -> list[ValidationIssue]:
    return _validate_cooking_graph(menu, strategy_aware=strategy_aware)
