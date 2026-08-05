"""Deterministic post-generation checks against WeeklyStrategy."""

from __future__ import annotations

from dataclasses import dataclass

from menu_models import MenuPlan, normalize_meal_name
from menu_validation import ALLERGY_ALIASES, parse_cook_time_minutes
from strategy.exceptions import StrategyComplianceError
from strategy.models import WeeklyStrategy

MEAL_TYPE_REPEAT_CODES = {
    "breakfast": "STRATEGY_REPEAT_BREAKFAST_EXCESSIVE",
    "lunch": "STRATEGY_REPEAT_LUNCH_EXCESSIVE",
    "dinner": "STRATEGY_REPEAT_DINNER_EXCESSIVE",
}

REPEAT_FLAGS = {
    "breakfast": "repeat_breakfasts",
    "lunch": "repeat_lunches",
    "dinner": "repeat_dinners",
}

MAX_EXACT_REPEATS_WHEN_DISABLED = 1


@dataclass(frozen=True)
class ComplianceIssue:
    code: str
    message: str
    path: str | None


def _expand_excluded_terms(products: list[str]) -> set[str]:
    terms: set[str] = set()
    for product in products:
        lowered = product.strip().lower()
        if not lowered:
            continue
        terms.add(lowered)
        alias_group = ALLERGY_ALIASES.get(lowered)
        if alias_group:
            terms.update(alias_group)
    return terms


def _contains_excluded_term(text: str, terms: set[str]) -> str | None:
    lowered = text.lower().replace("ё", "е")
    for term in terms:
        if term in lowered:
            return term
    return None


def validate_menu_against_strategy(
    menu: MenuPlan,
    strategy: WeeklyStrategy,
) -> None:
    """Raises StrategyComplianceError when menu violates strategy constraints."""
    issues: list[ComplianceIssue] = []

    _check_days(menu, strategy, issues)
    _check_meal_types(menu, strategy, issues)
    _check_excluded_products(menu, strategy, issues)
    _check_cooking_time(menu, strategy, issues)
    _check_meal_type_repeats(menu, strategy, issues)

    if not issues:
        from strategy.cooking_compliance import validate_cooking_contract

        try:
            validate_cooking_contract(menu, strategy)
        except StrategyComplianceError as exc:
            issues.extend(exc.issues)

    if issues:
        raise StrategyComplianceError(
            "Menu plan violates weekly strategy",
            issues=issues,
        )


def _check_days(menu: MenuPlan, strategy: WeeklyStrategy, issues: list[ComplianceIssue]) -> None:
    if len(menu.days_plan) != strategy.days:
        issues.append(
            ComplianceIssue(
                code="STRATEGY_DAYS_COUNT_MISMATCH",
                message=f"Expected {strategy.days} days, got {len(menu.days_plan)}",
                path="days_plan",
            )
        )


def _check_meal_types(menu: MenuPlan, strategy: WeeklyStrategy, issues: list[ComplianceIssue]) -> None:
    expected = set(strategy.meal_types)

    for day_index, day in enumerate(menu.days_plan):
        actual_types = [meal.type for meal in day.meals]
        actual_set = set(actual_types)

        if len(actual_types) != len(actual_set):
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_MEAL_TYPE_DUPLICATE",
                    message="Duplicate meal type within a day",
                    path=f"days_plan[{day_index}].meals",
                )
            )

        missing = expected - actual_set
        for meal_type in sorted(missing):
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_MEAL_TYPE_MISSING",
                    message=f"Missing required meal type '{meal_type}'",
                    path=f"days_plan[{day_index}].meals",
                )
            )

        unexpected = actual_set - expected
        for meal_type in sorted(unexpected):
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_MEAL_TYPE_UNEXPECTED",
                    message=f"Unexpected meal type '{meal_type}'",
                    path=f"days_plan[{day_index}].meals",
                )
            )


def _check_excluded_products(
    menu: MenuPlan,
    strategy: WeeklyStrategy,
    issues: list[ComplianceIssue],
) -> None:
    if not strategy.excluded_products:
        return

    terms = _expand_excluded_terms(strategy.excluded_products)

    for day_index, day in enumerate(menu.days_plan):
        for meal_index, meal in enumerate(day.meals):
            matched = _contains_excluded_term(meal.recipe_name, terms)
            if matched:
                issues.append(
                    ComplianceIssue(
                        code="STRATEGY_EXCLUDED_PRODUCT",
                        message=f"Excluded term '{matched}' found in meal name",
                        path=f"days_plan[{day_index}].meals[{meal_index}].recipe_name",
                    )
                )

    for recipe_index, recipe in enumerate(menu.recipes):
        for ingredient_index, ingredient in enumerate(recipe.ingredients):
            matched = _contains_excluded_term(ingredient.name, terms)
            if matched:
                issues.append(
                    ComplianceIssue(
                        code="STRATEGY_EXCLUDED_PRODUCT",
                        message=f"Excluded term '{matched}' found in ingredient",
                        path=f"recipes[{recipe_index}].ingredients[{ingredient_index}].name",
                    )
                )


def _check_cooking_time(
    menu: MenuPlan,
    strategy: WeeklyStrategy,
    issues: list[ComplianceIssue],
) -> None:
    limit = strategy.cooking_time_limit

    for recipe_index, recipe in enumerate(menu.recipes):
        minutes = parse_cook_time_minutes(recipe.cook_time)
        if minutes is None:
            continue
        if minutes > limit:
            issues.append(
                ComplianceIssue(
                    code="STRATEGY_COOKING_TIME_EXCEEDED",
                    message=(
                        f"Active cook_time {minutes} min exceeds strategy limit {limit} min"
                    ),
                    path=f"recipes[{recipe_index}].cook_time",
                )
            )


def _check_meal_type_repeats(
    menu: MenuPlan,
    strategy: WeeklyStrategy,
    issues: list[ComplianceIssue],
) -> None:
    if strategy.days <= 1:
        return

    for meal_type in ("breakfast", "lunch", "dinner"):
        flag_name = REPEAT_FLAGS[meal_type]
        if getattr(strategy, flag_name):
            continue

        counts: dict[str, int] = {}
        for day in menu.days_plan:
            for meal in day.meals:
                if meal.type != meal_type:
                    continue
                # Leftover servings are reuse, not independent recipe repeats.
                if meal.uses_leftovers:
                    continue
                key = normalize_meal_name(meal.recipe_name)
                if not key:
                    continue
                counts[key] = counts.get(key, 0) + 1

        for meal_name, count in counts.items():
            if count > MAX_EXACT_REPEATS_WHEN_DISABLED:
                issues.append(
                    ComplianceIssue(
                        code=MEAL_TYPE_REPEAT_CODES[meal_type],
                        message=(
                            f"Meal '{meal_name}' for {meal_type} appears {count} times "
                            f"but repeat_{meal_type}=false"
                        ),
                        path="days_plan",
                    )
                )
