"""Business-rule validation for normalized menu plans."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from menu_models import DayPlan, MenuPlan, Recipe, normalize_meal_name

Severity = Literal["error", "warning"]

BUDGET_TOLERANCE = 0.0
TOTAL_COST_MISMATCH_TOLERANCE = 1.0

# Canonical money quantum: every derived total is rounded to kopecks.
MONEY_QUANT = Decimal("0.01")

MAX_MEAL_REPEATS = 2
"""Maximum independent (non-leftover) uses of one meal in a plan."""


def _is_linked_leftover(meal, known_meal_ids: set[str]) -> bool:
    return bool(
        meal.uses_leftovers
        and meal.source_meal_id
        and meal.source_meal_id in known_meal_ids
        and meal.source_meal_id != meal.meal_id
    )


def build_meal_usage_inventory(menu_plan: MenuPlan) -> dict[str, object]:
    """Independent meal-name usage for deterministic replacement prompts.

    Leftover-linked meals do not count toward independent usage (same rule as
    MEAL_DUPLICATE_EXCESSIVE). Returned lists use display names for the model.
    """
    known_meal_ids = {
        meal.meal_id
        for day in menu_plan.days_plan
        for meal in day.meals
        if meal.meal_id
    }

    # key -> {display_name, count, meal_types: set}
    by_key: dict[str, dict[str, object]] = {}
    for day in menu_plan.days_plan:
        for meal in day.meals:
            if _is_linked_leftover(meal, known_meal_ids):
                continue
            key = normalize_meal_name(meal.recipe_name)
            if not key:
                continue
            entry = by_key.get(key)
            if entry is None:
                by_key[key] = {
                    "display_name": meal.recipe_name.strip(),
                    "count": 1,
                    "meal_types": {meal.type},
                }
            else:
                entry["count"] = int(entry["count"]) + 1
                meal_types = entry["meal_types"]
                if isinstance(meal_types, set):
                    meal_types.add(meal.type)

    used: list[dict[str, object]] = []
    at_limit: list[str] = []
    once_used: list[str] = []
    once_used_by_type: dict[str, list[str]] = {}

    for key in sorted(by_key.keys()):
        entry = by_key[key]
        display = str(entry["display_name"])
        count = int(entry["count"])
        types = sorted(entry["meal_types"]) if isinstance(entry["meal_types"], set) else []
        used.append({"name": display, "count": count, "meal_types": types})
        if count >= MAX_MEAL_REPEATS:
            at_limit.append(display)
        elif count == 1:
            once_used.append(display)
            for meal_type in types:
                once_used_by_type.setdefault(meal_type, []).append(display)

    return {
        "allowed_count": MAX_MEAL_REPEATS,
        "used": used,
        "at_limit": at_limit,
        "once_used": once_used,
        "once_used_by_type": once_used_by_type,
    }

COOKTIME_LIMITS_MINUTES: dict[str, int] = {
    "fast": 20,
    "medium": 45,
    "slow": 90,
}

PANTRY_STAPLES = frozenset(
    {
        "соль",
        "вода",
        "перец",
        "масло",
        "специи",
        "черный перец",
        "растительное масло",
        "оливковое масло",
        "подсолнечное масло",
    }
)

ALLERGY_ALIASES: dict[str, tuple[str, ...]] = {
    "молоко": ("молоко", "молочный", "молочные", "сыр", "творог", "сливки"),
    "глютен": ("глютен", "пшеница", "мука", "хлеб", "макароны"),
    "орехи": ("орех", "орехи", "арахис", "миндаль", "фундук"),
    "яйца": ("яйцо", "яйца", "яичный", "яичные"),
    "рыба": ("рыба", "рыбный", "лосось", "треска"),
    "морепродукты": ("креветка", "креветки", "мидии", "кальмар", "морепродукты"),
}


@dataclass(frozen=True)
class MenuValidationRequest:
    days: int
    budget: float
    meal_types: list[str]
    meals_per_day: int
    persons: int
    cooktime: str
    allergies: str
    strategy_aware: bool = False


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    path: str | None
    severity: Severity
    # Machine-readable sub-reason for diagnostics (e.g. PANTRY_CONTRACT_MISMATCH).
    reason_code: str | None = None
    # Structured diagnostics for targeted correction prompts and logging
    # (e.g. recipe_id, day indexes, occurrence counts). Never sent to clients.
    meta: dict[str, object] | None = None


@dataclass
class MenuValidationResult:
    menu_plan: MenuPlan | None
    errors: list[ValidationIssue]
    warnings: list[ValidationIssue]
    is_valid: bool


def parse_menu_plan(raw_data: dict[str, object]) -> MenuPlan:
    return MenuPlan.model_validate(raw_data)


def validate_menu_plan(
    menu_plan: MenuPlan,
    request: MenuValidationRequest,
    *,
    enforce_user_budget: bool = True,
) -> MenuValidationResult:
    """Validate menu structure and semantics.

    User weekly budget enforcement (`BUDGET_EXCEEDED`) uses ``menu_plan.total_cost``
    as the shopping-cost authority when ``enforce_user_budget=True``.

    For Claude responses that have not yet been rebuilt by BasketEngine, call with
    ``enforce_user_budget=False`` and run :func:`validate_shopping_budget` after
    basket rebuild (Sprint 10.8).
    """
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    _validate_structure(menu_plan, request, errors)
    _validate_meal_types(menu_plan, request, errors)
    _validate_meal_recipe_consistency(menu_plan, errors, warnings, request.strategy_aware)
    if enforce_user_budget:
        errors.extend(
            validate_shopping_budget(
                float(menu_plan.total_cost),
                float(request.budget),
            )
        )
    _validate_total_cost(menu_plan, errors)
    _validate_allergies(menu_plan, request, errors)
    _validate_cooktime(menu_plan, request, errors, warnings)
    _validate_duplicates(menu_plan, request, errors, warnings)
    _validate_basket_consistency(menu_plan, warnings)

    if request.strategy_aware:
        from cooking_identity import validate_cooking_instance_graph
        from recipe_identity import validate_ingredient_contributions, validate_recipe_graph

        for issue in validate_recipe_graph(menu_plan, strategy_aware=True):
            if issue.severity == "error":
                errors.append(issue)
            else:
                warnings.append(issue)
        for issue in validate_cooking_instance_graph(menu_plan, strategy_aware=True):
            errors.append(issue)
        for issue in validate_ingredient_contributions(menu_plan, strategy_aware=True):
            if issue.severity == "error":
                errors.append(issue)
            else:
                warnings.append(issue)

    is_valid = len(errors) == 0
    return MenuValidationResult(
        menu_plan=menu_plan if is_valid else None,
        errors=errors,
        warnings=warnings,
        is_valid=is_valid,
    )


def _issue(
    code: str,
    message: str,
    path: str | None,
    severity: Severity,
    meta: dict[str, object] | None = None,
) -> ValidationIssue:
    return ValidationIssue(code=code, message=message, path=path, severity=severity, meta=meta)


def quantize_money(value: Decimal) -> Decimal:
    """Canonical money rounding: kopecks, half-up."""
    return value.quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def compute_basket_total(menu_plan: MenuPlan) -> Decimal | None:
    """Derived total: sum of basket item prices with canonical rounding.

    Returns None if any price contribution is unusable so callers keep the
    original mismatch error instead of masking bad data.
    """
    total = Decimal("0")
    for category in menu_plan.basket:
        for item in category.items:
            price = item.price
            if isinstance(price, bool) or not isinstance(price, (int, float)):
                return None
            numeric = float(price)
            if not math.isfinite(numeric) or numeric < 0:
                return None
            total += Decimal(str(numeric))
    return quantize_money(total)


@dataclass(frozen=True)
class TotalCostNormalization:
    normalized: bool
    model_total: float
    calculated_total: float | None
    difference: float | None
    # Why normalization did not happen: "invalid_price_contributions" |
    # "already_consistent" | None (normalized).
    reason: str | None = None


def normalize_total_cost(menu_plan: MenuPlan) -> tuple[MenuPlan, TotalCostNormalization]:
    """Replaces the derived total_cost with the backend-calculated basket sum.

    total_cost is arithmetic over data the backend already has, so the model's
    own addition is never trusted. Individual item prices are never modified.
    """
    model_total = float(menu_plan.total_cost)
    calculated = compute_basket_total(menu_plan)
    if calculated is None:
        return menu_plan, TotalCostNormalization(
            normalized=False,
            model_total=model_total,
            calculated_total=None,
            difference=None,
            reason="invalid_price_contributions",
        )

    calculated_total = float(calculated)
    difference = float(quantize_money(Decimal(str(abs(model_total - calculated_total)))))
    if difference == 0.0:
        return menu_plan, TotalCostNormalization(
            normalized=False,
            model_total=model_total,
            calculated_total=calculated_total,
            difference=0.0,
            reason="already_consistent",
        )

    updated = menu_plan.model_copy(update={"total_cost": calculated_total})
    return updated, TotalCostNormalization(
        normalized=True,
        model_total=model_total,
        calculated_total=calculated_total,
        difference=difference,
    )


def _validate_structure(
    menu_plan: MenuPlan,
    request: MenuValidationRequest,
    errors: list[ValidationIssue],
) -> None:
    if len(menu_plan.days_plan) != request.days:
        errors.append(
            _issue(
                "DAYS_COUNT_MISMATCH",
                f"Expected {request.days} days, got {len(menu_plan.days_plan)}",
                "days_plan",
                "error",
            )
        )


def _validate_meal_types(
    menu_plan: MenuPlan,
    request: MenuValidationRequest,
    errors: list[ValidationIssue],
) -> None:
    expected = set(request.meal_types)

    for day_index, day in enumerate(menu_plan.days_plan):
        actual_types = [meal.type for meal in day.meals]
        actual_set = set(actual_types)

        if len(actual_types) != len(actual_set):
            errors.append(
                _issue(
                    "MEAL_TYPE_DUPLICATE",
                    "Duplicate meal type within a day",
                    f"days_plan[{day_index}].meals",
                    "error",
                )
            )

        missing = expected - actual_set
        for meal_type in sorted(missing):
            errors.append(
                _issue(
                    "MEAL_TYPE_MISSING",
                    f"Missing required meal type '{meal_type}'",
                    f"days_plan[{day_index}].meals",
                    "error",
                )
            )

        unexpected = actual_set - expected
        for meal_type in sorted(unexpected):
            errors.append(
                _issue(
                    "MEAL_TYPE_UNEXPECTED",
                    f"Unexpected meal type '{meal_type}'",
                    f"days_plan[{day_index}].meals",
                    "error",
                )
            )


def _find_recipe_indices(meal_name: str, recipes: list[Recipe]) -> list[int]:
    trimmed = meal_name.strip()
    if not trimmed:
        return []

    normalized_meal = normalize_meal_name(trimmed)
    exact_matches: list[int] = []
    normalized_matches: list[int] = []

    for index, recipe in enumerate(recipes):
        if recipe.name.strip().lower() == trimmed.lower():
            exact_matches.append(index)
        elif normalize_meal_name(recipe.name) == normalized_meal:
            normalized_matches.append(index)

    if len(exact_matches) == 1:
        return exact_matches
    if len(exact_matches) > 1:
        return exact_matches
    if len(normalized_matches) == 1:
        return normalized_matches
    return normalized_matches


def _validate_meal_recipe_consistency(
    menu_plan: MenuPlan,
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
    strategy_aware: bool = False,
) -> None:
    from recipe_identity import find_recipe_by_id, find_recipe_index_by_id, resolve_recipe_for_meal

    used_recipe_indices: set[int] = set()

    for day_index, day in enumerate(menu_plan.days_plan):
        for meal_index, meal in enumerate(day.meals):
            path = f"days_plan[{day_index}].meals[{meal_index}]"

            if meal.recipe_id:
                recipe = find_recipe_by_id(menu_plan.recipes, meal.recipe_id)
                if recipe is None:
                    errors.append(
                        _issue(
                            "MEAL_RECIPE_NOT_FOUND",
                            f"No recipe for recipe_id '{meal.recipe_id}'",
                            path,
                            "error",
                        )
                    )
                else:
                    idx = find_recipe_index_by_id(menu_plan.recipes, meal.recipe_id)
                    if idx is not None:
                        used_recipe_indices.add(idx)
                continue

            recipe, code = resolve_recipe_for_meal(meal, menu_plan.recipes, path=path)
            if code == "MEAL_RECIPE_AMBIGUOUS":
                severity: Severity = "error" if strategy_aware else "warning"
                target = errors if strategy_aware else warnings
                target.append(
                    _issue(
                        "MEAL_RECIPE_AMBIGUOUS",
                        f"Ambiguous recipe match for meal '{meal.recipe_name}'",
                        path,
                        severity,
                    )
                )
            elif code == "MEAL_RECIPE_MISSING" or recipe is None:
                errors.append(
                    _issue(
                        "MEAL_RECIPE_MISSING",
                        f"No recipe match for meal '{meal.recipe_name}'",
                        path,
                        "error",
                    )
                )
            elif recipe is not None:
                for idx, candidate in enumerate(menu_plan.recipes):
                    if candidate.name == recipe.name:
                        used_recipe_indices.add(idx)
                        break

    for index, recipe in enumerate(menu_plan.recipes):
        if index not in used_recipe_indices:
            warnings.append(
                _issue(
                    "RECIPE_UNUSED",
                    f"Recipe '{recipe.name}' is not referenced in days_plan",
                    f"recipes[{index}]",
                    "warning",
                )
            )


def validate_shopping_budget(
    shopping_cost: float,
    budget_limit: float,
    *,
    path: str = "shopping_cost",
) -> list[ValidationIssue]:
    """Hard weekly budget gate — authoritative metric is BasketEngine shopping_cost.

    ``model_total`` and recipe/calculated totals must not call this with their values.
    After BasketEngine rebuild, ``MenuPlan.total_cost`` holds shopping_cost on the wire.
    """
    errors: list[ValidationIssue] = []
    if not math.isfinite(shopping_cost) or not math.isfinite(budget_limit):
        errors.append(
            _issue(
                "BUDGET_EXCEEDED",
                "shopping_cost or budget_limit is not a finite number",
                path,
                "error",
                meta={
                    "shopping_cost": shopping_cost,
                    "budget_limit": budget_limit,
                    "authoritative_metric": "shopping_cost",
                },
            )
        )
        return errors

    limit = float(budget_limit) + BUDGET_TOLERANCE
    if float(shopping_cost) > limit:
        overshoot = round(float(shopping_cost) - float(budget_limit), 2)
        errors.append(
            _issue(
                "BUDGET_EXCEEDED",
                (
                    f"shopping_cost {shopping_cost} exceeds budget_limit {budget_limit}"
                ),
                path,
                "error",
                meta={
                    "shopping_cost": float(shopping_cost),
                    "budget_limit": float(budget_limit),
                    "overshoot_amount": overshoot,
                    "authoritative_metric": "shopping_cost",
                },
            )
        )
    return errors


def _validate_budget(
    menu_plan: MenuPlan,
    request: MenuValidationRequest,
    errors: list[ValidationIssue],
) -> None:
    """Legacy helper — delegates to shopping-budget authority on total_cost."""
    errors.extend(
        validate_shopping_budget(
            float(menu_plan.total_cost),
            float(request.budget),
            path="total_cost",
        )
    )


def _validate_total_cost(menu_plan: MenuPlan, errors: list[ValidationIssue]) -> None:
    basket_total = sum(item.price for category in menu_plan.basket for item in category.items)
    delta = abs(menu_plan.total_cost - basket_total)
    if delta > TOTAL_COST_MISMATCH_TOLERANCE:
        errors.append(
            _issue(
                "TOTAL_COST_MISMATCH",
                f"total_cost {menu_plan.total_cost} differs from basket sum {basket_total}",
                "total_cost",
                "error",
            )
        )


def _parse_allergies(allergies: str) -> list[str]:
    if not allergies or allergies.strip().lower() == "нет":
        return []

    parts = re.split(r"[,;]+", allergies)
    return [part.strip().lower() for part in parts if part.strip()]


def _expand_allergy_terms(allergies: list[str]) -> set[str]:
    terms: set[str] = set()
    for allergy in allergies:
        terms.add(allergy)
        alias_group = ALLERGY_ALIASES.get(allergy)
        if alias_group:
            terms.update(alias_group)
    return terms


def _contains_allergy_term(text: str, terms: set[str]) -> str | None:
    lowered = text.lower().replace("ё", "е")
    for term in terms:
        if term in lowered:
            return term
    return None


def _validate_allergies(
    menu_plan: MenuPlan,
    request: MenuValidationRequest,
    errors: list[ValidationIssue],
) -> None:
    allergy_terms = _expand_allergy_terms(_parse_allergies(request.allergies))
    if not allergy_terms:
        return

    for day_index, day in enumerate(menu_plan.days_plan):
        for meal_index, meal in enumerate(day.meals):
            matched = _contains_allergy_term(meal.recipe_name, allergy_terms)
            if matched:
                errors.append(
                    _issue(
                        "ALLERGY_VIOLATION",
                        f"Allergen term '{matched}' found in meal name",
                        f"days_plan[{day_index}].meals[{meal_index}].recipe_name",
                        "error",
                    )
                )

    for recipe_index, recipe in enumerate(menu_plan.recipes):
        for ingredient_index, ingredient in enumerate(recipe.ingredients):
            matched = _contains_allergy_term(ingredient.name, allergy_terms)
            if matched:
                errors.append(
                    _issue(
                        "ALLERGY_VIOLATION",
                        f"Allergen term '{matched}' found in recipe ingredient",
                        f"recipes[{recipe_index}].ingredients[{ingredient_index}].name",
                        "error",
                    )
                )

    for category_index, category in enumerate(menu_plan.basket):
        for item_index, item in enumerate(category.items):
            matched = _contains_allergy_term(item.name, allergy_terms)
            if matched:
                errors.append(
                    _issue(
                        "ALLERGY_VIOLATION",
                        f"Allergen term '{matched}' found in basket item",
                        f"basket[{category_index}].items[{item_index}].name",
                        "error",
                    )
                )


_COOKTIME_PATTERN = re.compile(
    r"(\d+)\s*(?:-|–|—)?\s*(\d+)?\s*(?:мин|минут|минуты|минуту|m|min)?",
    re.IGNORECASE,
)


def parse_cook_time_minutes(cook_time: str) -> int | None:
    text = cook_time.strip().lower().replace("ё", "е")
    if not text:
        return None

    if text.isdigit():
        return int(text)

    match = _COOKTIME_PATTERN.search(text)
    if not match:
        return None

    first = int(match.group(1))
    second = int(match.group(2)) if match.group(2) else None
    return second if second is not None else first


def _meal_ids_for_recipe(menu_plan: MenuPlan, recipe: Recipe) -> list[str]:
    """meal_ids (or positional fallbacks) of meals linked to this recipe."""
    normalized_name = normalize_meal_name(recipe.name)
    linked: list[str] = []
    for day_index, day in enumerate(menu_plan.days_plan):
        for meal in day.meals:
            if recipe.recipe_id and meal.recipe_id:
                if meal.recipe_id != recipe.recipe_id:
                    continue
            elif normalize_meal_name(meal.recipe_name) != normalized_name:
                continue
            linked.append(meal.meal_id or f"day{day_index + 1}_{meal.type}")
    return linked


def _validate_cooktime(
    menu_plan: MenuPlan,
    request: MenuValidationRequest,
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
) -> None:
    limit = COOKTIME_LIMITS_MINUTES.get(request.cooktime)
    if limit is None:
        return

    for index, recipe in enumerate(menu_plan.recipes):
        minutes = parse_cook_time_minutes(recipe.cook_time)
        if minutes is None:
            warnings.append(
                _issue(
                    "COOKTIME_UNPARSEABLE",
                    f"Could not parse cook_time '{recipe.cook_time}'",
                    f"recipes[{index}].cook_time",
                    "warning",
                )
            )
            continue

        if minutes > limit:
            recipe_ref = recipe.recipe_id or recipe.name
            errors.append(
                _issue(
                    "COOKTIME_EXCEEDED",
                    (
                        f"Recipe '{recipe_ref}' ({recipe.name}) cook_time {minutes} min "
                        f"exceeds limit {limit} min for '{request.cooktime}'"
                    ),
                    f"recipes[{index}].cook_time",
                    "error",
                    meta={
                        "recipe_id": recipe.recipe_id,
                        "recipe_title": recipe.name,
                        "actual_minutes": minutes,
                        "allowed_minutes": limit,
                        "cooktime_mode": request.cooktime,
                        "meal_ids": _meal_ids_for_recipe(menu_plan, recipe),
                    },
                )
            )


def _validate_duplicates(
    menu_plan: MenuPlan,
    request: MenuValidationRequest,
    errors: list[ValidationIssue],
    warnings: list[ValidationIssue],
) -> None:
    if request.days <= 1:
        return

    known_meal_ids = {
        meal.meal_id
        for day in menu_plan.days_plan
        for meal in day.meals
        if meal.meal_id
    }

    occurrences: dict[str, list[dict[str, object]]] = {}
    for day_index, day in enumerate(menu_plan.days_plan):
        for meal_index, meal in enumerate(day.meals):
            key = normalize_meal_name(meal.recipe_name)
            if not key:
                continue
            # A leftover correctly linked to another meal in the plan is an
            # intentional reuse allowed by the cooking contract, not an
            # independent duplicate.
            linked_leftover = _is_linked_leftover(meal, known_meal_ids)
            occurrences.setdefault(key, []).append(
                {
                    "day_number": day_index + 1,
                    "meal_index": meal_index,
                    "meal_id": meal.meal_id,
                    "meal_type": meal.type,
                    "recipe_name": meal.recipe_name,
                    "linked_leftover": linked_leftover,
                }
            )

    for key, entries in occurrences.items():
        independent = [entry for entry in entries if not entry["linked_leftover"]]
        independent_count = len(independent)
        leftover_count = len(entries) - independent_count
        if independent_count <= 1:
            continue

        meta: dict[str, object] = {
            "duplicate_key": key,
            "meal_name": str(entries[0]["recipe_name"]),
            "meal_types": sorted({str(entry["meal_type"]) for entry in entries}),
            "occurrence_count": len(entries),
            "independent_count": independent_count,
            "leftover_count": leftover_count,
            "allowed_count": MAX_MEAL_REPEATS,
            "day_numbers": [entry["day_number"] for entry in entries],
            "meal_ids": [entry["meal_id"] for entry in entries],
            "independent_positions": [
                {
                    "day": entry["day_number"],
                    "meal_type": entry["meal_type"],
                    "meal_id": entry["meal_id"],
                }
                for entry in independent
            ],
        }

        if independent_count <= MAX_MEAL_REPEATS:
            warnings.append(
                _issue(
                    "MEAL_DUPLICATE_WARNING",
                    f"Meal '{key}' appears {independent_count} times in the plan",
                    "days_plan",
                    "warning",
                    meta=meta,
                )
            )
        else:
            meta["replacements_needed"] = independent_count - MAX_MEAL_REPEATS
            errors.append(
                _issue(
                    "MEAL_DUPLICATE_EXCESSIVE",
                    (
                        f"Meal '{key}' appears {independent_count} times independently "
                        f"(+{leftover_count} leftover-linked), allowed {MAX_MEAL_REPEATS}"
                    ),
                    "days_plan",
                    "error",
                    meta=meta,
                )
            )


_WEIGHT_SUFFIX_PATTERN = re.compile(
    r"\s+\d+[\d,.]*\s*(?:г|гр|кг|ml|мл|л|шт)\.?$",
    re.IGNORECASE,
)


def normalize_product_name(name: str) -> str:
    normalized = normalize_meal_name(name)
    normalized = _WEIGHT_SUFFIX_PATTERN.sub("", normalized).strip()
    return normalized


def _is_pantry_staple(name: str) -> bool:
    normalized = normalize_product_name(name)
    if normalized in PANTRY_STAPLES:
        return True
    return any(staple in normalized for staple in PANTRY_STAPLES)


def _validate_basket_consistency(
    menu_plan: MenuPlan,
    warnings: list[ValidationIssue],
) -> None:
    basket_names = {
        normalize_product_name(item.name)
        for category in menu_plan.basket
        for item in category.items
        if normalize_product_name(item.name)
    }

    for recipe_index, recipe in enumerate(menu_plan.recipes):
        for ingredient_index, ingredient in enumerate(recipe.ingredients):
            ingredient_name = ingredient.name.strip()
            if not ingredient_name or _is_pantry_staple(ingredient_name):
                continue

            normalized_ingredient = normalize_product_name(ingredient_name)
            if not normalized_ingredient:
                continue

            if normalized_ingredient not in basket_names:
                warnings.append(
                    _issue(
                        "BASKET_INGREDIENT_MISSING",
                        f"Ingredient '{ingredient_name}' not found in basket",
                        f"recipes[{recipe_index}].ingredients[{ingredient_index}].name",
                        "warning",
                    )
                )
