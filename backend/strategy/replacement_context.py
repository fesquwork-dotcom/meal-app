"""Build replacement context and validate incoming menu against strategy record."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from menu_models import DayMeal, MenuPlan, Recipe
from recipe_identity import find_recipe_by_id, resolve_recipe_for_meal
from menu_validation import MenuValidationRequest, validate_menu_plan
from strategy.compliance import validate_menu_against_strategy
from strategy.cooking_compliance import MealRef, _collect_meal_refs, validate_cooking_contract
from strategy.exceptions import StrategyComplianceError
from strategy.lifecycle import is_strategy_completed
from strategy.models import WeeklyStrategy
from strategy.records import StrategyRecord, StrategyStatus
from strategy.replacement_constants import MAX_AFFECTED_MEALS, MAX_MENU_PLAN_DAYS
from strategy.replacement_exceptions import (
    MealNotFoundError,
    MenuStrategyMismatchError,
    ReplacementScopeError,
    ReplacementValidationError,
    StrategyNotActiveError,
)


@dataclass(frozen=True)
class TargetMealContext:
    meal_ref: MealRef
    day_number: int
    recipe: Recipe | None
    downstream_refs: tuple[MealRef, ...]


@dataclass(frozen=True)
class ReplacementContext:
    strategy: WeeklyStrategy
    record: StrategyRecord
    menu_plan: MenuPlan
    target: TargetMealContext
    validation_request: MenuValidationRequest


def _find_recipe_for_meal(menu_plan: MenuPlan, meal: DayMeal) -> Recipe | None:
    if meal.recipe_id:
        return find_recipe_by_id(menu_plan.recipes, meal.recipe_id)
    recipe, code = resolve_recipe_for_meal(meal, menu_plan.recipes, path="")
    if code in {"MEAL_RECIPE_AMBIGUOUS", "MEAL_RECIPE_MISSING"}:
        return None
    return recipe


def find_meal_by_id(menu_plan: MenuPlan, meal_id: str) -> MealRef:
    refs = _collect_meal_refs(menu_plan)
    matches = [ref for ref in refs if ref.meal.meal_id == meal_id]
    if len(matches) == 0:
        raise MealNotFoundError(meal_id)
    if len(matches) > 1:
        raise MenuStrategyMismatchError(
            "MEAL_ID_DUPLICATE",
            f"Duplicate meal_id '{meal_id}' in menu plan",
        )
    return matches[0]


def find_downstream_meals(menu_plan: MenuPlan, target_meal_id: str) -> list[MealRef]:
    refs = _collect_meal_refs(menu_plan)
    return [ref for ref in refs if ref.meal.source_meal_id == target_meal_id]


def assert_strategy_active(record: StrategyRecord, current_date: date | None = None) -> None:
    today = current_date or date.today()
    if is_strategy_completed(record, today):
        raise StrategyNotActiveError(StrategyStatus.COMPLETED.value)
    if record.status != StrategyStatus.ACTIVE.value:
        raise StrategyNotActiveError(record.status)


def validate_menu_strategy_binding(
    menu_plan: MenuPlan,
    strategy_id: str,
    record: StrategyRecord,
    strategy: WeeklyStrategy,
) -> None:
    if menu_plan.strategy_id != strategy_id:
        raise MenuStrategyMismatchError(
            "MENU_STRATEGY_ID_MISMATCH",
            "menu_plan.strategy_id does not match request strategy_id",
        )

    if menu_plan.plan_start_date is None:
        raise MenuStrategyMismatchError(
            "MENU_PLAN_START_DATE_MISSING",
            "menu_plan.plan_start_date is required for strategy-backed replacement",
        )

    if menu_plan.plan_start_date.isoformat() != record.plan_start_date:
        raise MenuStrategyMismatchError(
            "MENU_PLAN_START_DATE_MISMATCH",
            "menu_plan.plan_start_date does not match strategy record",
        )

    if len(menu_plan.days_plan) != record.plan_days:
        raise MenuStrategyMismatchError(
            "MENU_DAYS_COUNT_MISMATCH",
            "menu_plan days count does not match strategy record",
        )

    if len(menu_plan.days_plan) > MAX_MENU_PLAN_DAYS:
        raise MenuStrategyMismatchError(
            "MENU_PLAN_TOO_LARGE",
            f"menu_plan exceeds maximum {MAX_MENU_PLAN_DAYS} days",
        )

    if strategy.days != record.plan_days:
        raise MenuStrategyMismatchError(
            "STRATEGY_DAYS_MISMATCH",
            "strategy snapshot days do not match record",
        )


def validate_incoming_menu(
    menu_plan: MenuPlan,
    strategy: WeeklyStrategy,
    validation_request: MenuValidationRequest,
) -> None:
    result = validate_menu_plan(menu_plan, validation_request)
    if not result.is_valid:
        codes = [issue.code for issue in result.errors]
        raise ReplacementValidationError(
            "Incoming menu plan failed validation",
            issue_codes=codes,
        )

    try:
        validate_menu_against_strategy(menu_plan, strategy)
        validate_cooking_contract(menu_plan, strategy)
    except StrategyComplianceError as exc:
        raise ReplacementValidationError(
            "Incoming menu plan failed strategy compliance",
            issue_codes=exc.issue_codes,
        ) from exc


def build_replacement_context(
    *,
    menu_plan: MenuPlan,
    strategy_id: str,
    meal_id: str,
    record: StrategyRecord,
    strategy: WeeklyStrategy,
    validation_request: MenuValidationRequest,
    current_date: date | None = None,
) -> ReplacementContext:
    assert_strategy_active(record, current_date)
    validate_menu_strategy_binding(menu_plan, strategy_id, record, strategy)
    validate_incoming_menu(menu_plan, strategy, validation_request)

    target_ref = find_meal_by_id(menu_plan, meal_id)
    downstream = find_downstream_meals(menu_plan, meal_id)

    if len(downstream) > MAX_AFFECTED_MEALS:
        raise ReplacementScopeError(
            f"Meal has {len(downstream)} downstream dependencies; "
            f"maximum allowed is {MAX_AFFECTED_MEALS}",
        )

    target_recipe = _find_recipe_for_meal(menu_plan, target_ref.meal)

    return ReplacementContext(
        strategy=strategy,
        record=record,
        menu_plan=menu_plan,
        target=TargetMealContext(
            meal_ref=target_ref,
            day_number=target_ref.day_index + 1,
            recipe=target_recipe,
            downstream_refs=tuple(downstream),
        ),
        validation_request=validation_request,
    )
