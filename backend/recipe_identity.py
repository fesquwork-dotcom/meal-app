"""Recipe ID assignment, usage graph, and ingredient contribution validation."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Literal

from menu_models import DayMeal, MenuPlan, Recipe, RecipeIngredient, normalize_meal_name
from menu_validation import PANTRY_STAPLES, ValidationIssue, _find_recipe_indices, _is_pantry_staple

logger = logging.getLogger(__name__)

RECIPE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,80}$")
MAX_RECIPES = 200

ContributionType = Literal["purchase", "from_source", "pantry"]
VALID_CONTRIBUTIONS = frozenset({"purchase", "from_source", "pantry"})

# Sub-reasons for INGREDIENT_CONTRIBUTION_INVALID diagnostics.
CONTRIBUTION_REASON_NOT_ALLOWLISTED = "CONTRIBUTION_VALUE_NOT_ALLOWLISTED"
CONTRIBUTION_REASON_PANTRY_MISMATCH = "PANTRY_CONTRACT_MISMATCH"

_SAFE_LABEL_MAX_LENGTH = 40
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x1f\x7f]")


def _safe_ingredient_label(name: object) -> str:
    """Development-only ingredient label: sanitized and truncated."""
    if not isinstance(name, str):
        return f"<{type(name).__name__}>"
    cleaned = _CONTROL_CHARS_RE.sub(" ", name).strip()
    return cleaned[:_SAFE_LABEL_MAX_LENGTH] or "<empty>"


def _log_contribution_diagnostic(
    *,
    reason: str,
    recipe_index: int,
    ingredient_index: int,
    ingredient_name: object,
    contribution_state: str,
) -> None:
    """Privacy-safe structured event for INGREDIENT_CONTRIBUTION_INVALID.

    Ingredient label is included only outside production; production sees
    indices, reason, and contribution state only.
    """
    import config

    if config.ENVIRONMENT == "production":
        logger.warning(
            "ingredient_contribution_invalid recipe_index=%s ingredient_index=%s "
            "contribution_state=%s validation_reason=%s",
            recipe_index,
            ingredient_index,
            contribution_state,
            reason,
        )
        return
    logger.warning(
        "ingredient_contribution_invalid recipe_index=%s ingredient_index=%s "
        "ingredient_label=%s contribution_state=%s validation_reason=%s",
        recipe_index,
        ingredient_index,
        _safe_ingredient_label(ingredient_name),
        contribution_state,
        reason,
    )


def is_valid_recipe_id(recipe_id: str | None) -> bool:
    if not recipe_id or not isinstance(recipe_id, str):
        return False
    stripped = recipe_id.strip()
    return bool(stripped and RECIPE_ID_PATTERN.match(stripped))


def sanitize_recipe_id(recipe_id: str | None) -> str | None:
    if not recipe_id or not isinstance(recipe_id, str):
        return None
    stripped = recipe_id.strip()
    if is_valid_recipe_id(stripped):
        return stripped
    return None


def default_recipe_id_for_meal(meal: DayMeal, day_index: int) -> str:
    if meal.meal_id and is_valid_recipe_id(f"recipe_{meal.meal_id}"):
        return f"recipe_{meal.meal_id}"
    return f"recipe_day{day_index + 1}_{meal.type}"


@dataclass(frozen=True)
class RecipeUsageGraph:
    recipe_id_to_meal_ids: dict[str, list[str]]
    recipe_id_to_recipe: dict[str, Recipe]
    meal_id_to_recipe_id: dict[str, str]


def build_recipe_usage_graph(menu: MenuPlan) -> RecipeUsageGraph:
    recipe_id_to_recipe: dict[str, Recipe] = {}
    for recipe in menu.recipes:
        if recipe.recipe_id and is_valid_recipe_id(recipe.recipe_id):
            recipe_id_to_recipe[recipe.recipe_id] = recipe

    recipe_id_to_meal_ids: dict[str, list[str]] = {}
    meal_id_to_recipe_id: dict[str, str] = {}

    for day in menu.days_plan:
        for meal in day.meals:
            if not meal.recipe_id:
                continue
            meal_key = meal.meal_id or f"{meal.type}:{meal.recipe_name}"
            meal_id_to_recipe_id[meal_key] = meal.recipe_id
            recipe_id_to_meal_ids.setdefault(meal.recipe_id, []).append(meal_key)

    return RecipeUsageGraph(
        recipe_id_to_meal_ids=recipe_id_to_meal_ids,
        recipe_id_to_recipe=recipe_id_to_recipe,
        meal_id_to_recipe_id=meal_id_to_recipe_id,
    )


def find_recipe_by_id(recipes: list[Recipe], recipe_id: str) -> Recipe | None:
    matches = [recipe for recipe in recipes if recipe.recipe_id == recipe_id]
    if len(matches) == 1:
        return matches[0]
    return None


def find_recipe_index_by_id(recipes: list[Recipe], recipe_id: str) -> int | None:
    indices = [idx for idx, recipe in enumerate(recipes) if recipe.recipe_id == recipe_id]
    if len(indices) == 1:
        return indices[0]
    return None


def is_recipe_id_referenced(menu: MenuPlan, recipe_id: str) -> bool:
    for day in menu.days_plan:
        for meal in day.meals:
            if meal.recipe_id == recipe_id:
                return True
    return False


def resolve_recipe_for_meal(
    meal: DayMeal,
    recipes: list[Recipe],
    *,
    path: str,
) -> tuple[Recipe | None, str | None]:
    """Resolves recipe by recipe_id first, then legacy name lookup."""
    if meal.recipe_id:
        recipe = find_recipe_by_id(recipes, meal.recipe_id)
        if recipe is None:
            return None, "MEAL_RECIPE_NOT_FOUND"
        if normalize_meal_name(recipe.name) != normalize_meal_name(meal.recipe_name):
            if recipe.name.strip().lower() != meal.recipe_name.strip().lower():
                return recipe, "MEAL_RECIPE_NAME_MISMATCH"
        return recipe, None

    matches = _find_recipe_indices(meal.recipe_name, recipes)
    if len(matches) == 0:
        return None, "MEAL_RECIPE_MISSING"
    if len(matches) > 1:
        return None, "MEAL_RECIPE_AMBIGUOUS"
    return recipes[matches[0]], None


def meal_has_contribution_roles(recipe: Recipe) -> bool:
    return any(ingredient.contribution in VALID_CONTRIBUTIONS for ingredient in recipe.ingredients)


def normalize_pantry_contribution(ingredient: RecipeIngredient) -> ContributionType:
    """Trust boundary: pantry only for registered staples."""
    canonical = ingredient.name.strip().lower().replace("ё", "е")
    if canonical in PANTRY_STAPLES:
        return "pantry"
    for staple in PANTRY_STAPLES:
        if staple in canonical:
            return "pantry"
    return "purchase"


def effective_contribution(meal: DayMeal, ingredient: RecipeIngredient) -> ContributionType | None:
    """Returns effective contribution; None means skip ingredient (legacy leftover meal)."""
    raw = ingredient.contribution
    if raw in VALID_CONTRIBUTIONS:
        if raw == "pantry":
            return normalize_pantry_contribution(ingredient)
        return raw

    if meal.uses_leftovers:
        return None

    if _is_pantry_staple(ingredient.name):
        return "pantry"
    return "purchase"


def assign_and_validate_recipe_ids(
    menu: MenuPlan,
    *,
    strategy_aware: bool,
) -> tuple[MenuPlan, list[ValidationIssue]]:
    """Deterministically assigns missing recipe IDs and returns validation issues."""
    errors: list[ValidationIssue] = []
    warnings: list[ValidationIssue] = []

    recipes = [recipe.model_copy() for recipe in menu.recipes]
    days_plan = [day.model_copy() for day in menu.days_plan]

    if len(recipes) > MAX_RECIPES:
        errors.append(
            ValidationIssue(
                code="RECIPE_ID_DUPLICATE",
                message=f"Recipe count exceeds limit {MAX_RECIPES}",
                path="recipes",
                severity="error",
            )
        )

    for idx, recipe in enumerate(recipes):
        sanitized = sanitize_recipe_id(recipe.recipe_id)
        if recipe.recipe_id and sanitized is None:
            recipes[idx] = recipe.model_copy(update={"recipe_id": None})
        elif sanitized:
            recipes[idx] = recipe.model_copy(update={"recipe_id": sanitized})

    for day_index, day in enumerate(days_plan):
        for meal_index, meal in enumerate(day.meals):
            path = f"days_plan[{day_index}].meals[{meal_index}]"
            sanitized_meal_id = sanitize_recipe_id(meal.recipe_id)
            if meal.recipe_id and sanitized_meal_id is None:
                day.meals[meal_index] = meal.model_copy(update={"recipe_id": None})
                meal = day.meals[meal_index]
            elif sanitized_meal_id:
                day.meals[meal_index] = meal.model_copy(update={"recipe_id": sanitized_meal_id})
                meal = day.meals[meal_index]

            if not meal.recipe_id:
                name_matches = _find_recipe_indices(meal.recipe_name, recipes)
                if len(name_matches) > 1:
                    if strategy_aware:
                        errors.append(
                            ValidationIssue(
                                code="MEAL_RECIPE_AMBIGUOUS",
                                message=f"Ambiguous recipe name '{meal.recipe_name}' without recipe_id",
                                path=path,
                                severity="error",
                            )
                        )
                    else:
                        warnings.append(
                            ValidationIssue(
                                code="MEAL_RECIPE_AMBIGUOUS",
                                message=f"Ambiguous legacy recipe name '{meal.recipe_name}'",
                                path=path,
                                severity="warning",
                            )
                        )
                    continue

                if len(name_matches) == 1:
                    linked = recipes[name_matches[0]]
                    if linked.recipe_id:
                        day.meals[meal_index] = meal.model_copy(update={"recipe_id": linked.recipe_id})
                        continue

                assigned_id = default_recipe_id_for_meal(meal, day_index)
                day.meals[meal_index] = meal.model_copy(update={"recipe_id": assigned_id})
                if len(name_matches) == 1:
                    recipes[name_matches[0]] = recipes[name_matches[0]].model_copy(
                        update={"recipe_id": assigned_id}
                    )

    id_to_indices: dict[str, list[int]] = {}
    for idx, recipe in enumerate(recipes):
        if not recipe.recipe_id:
            if strategy_aware:
                errors.append(
                    ValidationIssue(
                        code="RECIPE_ID_MISSING",
                        message=f"Recipe '{recipe.name}' missing recipe_id",
                        path=f"recipes[{idx}]",
                        severity="error",
                    )
                )
            continue
        id_to_indices.setdefault(recipe.recipe_id, []).append(idx)

    for recipe_id, indices in id_to_indices.items():
        if len(indices) > 1:
            errors.append(
                ValidationIssue(
                    code="RECIPE_ID_DUPLICATE",
                    message=f"Duplicate recipe_id '{recipe_id}'",
                    path=f"recipes[{indices[0]}]",
                    severity="error",
                )
            )

    referenced_ids: set[str] = set()
    for day_index, day in enumerate(days_plan):
        for meal_index, meal in enumerate(day.meals):
            path = f"days_plan[{day_index}].meals[{meal_index}]"
            if not meal.recipe_id:
                if strategy_aware:
                    errors.append(
                        ValidationIssue(
                            code="MEAL_RECIPE_ID_MISSING",
                            message="Strategy-aware meal missing recipe_id",
                            path=path,
                            severity="error",
                        )
                    )
                continue

            referenced_ids.add(meal.recipe_id)
            if meal.recipe_id not in id_to_indices:
                errors.append(
                    ValidationIssue(
                        code="MEAL_RECIPE_NOT_FOUND",
                        message=f"Meal references missing recipe_id '{meal.recipe_id}'",
                        path=path,
                        severity="error",
                    )
                )
                continue

            recipe = recipes[id_to_indices[meal.recipe_id][0]]
            if (
                normalize_meal_name(recipe.name) != normalize_meal_name(meal.recipe_name)
                and recipe.name.strip().lower() != meal.recipe_name.strip().lower()
            ):
                if strategy_aware:
                    errors.append(
                        ValidationIssue(
                            code="MEAL_RECIPE_NAME_MISMATCH",
                            message=(
                                f"Meal recipe_name '{meal.recipe_name}' "
                                f"does not match recipe '{recipe.name}'"
                            ),
                            path=path,
                            severity="error",
                        )
                    )

    if strategy_aware:
        recipes = [
            recipe
            for recipe in recipes
            if recipe.recipe_id and recipe.recipe_id in referenced_ids
        ]
    else:
        orphan_count = sum(
            1 for recipe in recipes if recipe.recipe_id and recipe.recipe_id not in referenced_ids
        )
        if orphan_count:
            logger.info("recipe_graph orphan_recipes=%s ambiguous_legacy=%s", orphan_count, 0)

    updated = menu.model_copy(update={"recipes": recipes, "days_plan": days_plan})
    issues = errors + warnings
    return updated, issues


def validate_ingredient_contributions(
    menu: MenuPlan,
    *,
    strategy_aware: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    meal_refs_by_id: dict[str, tuple[int, int, DayMeal]] = {}
    recipe_index_by_identity = {id(recipe): idx for idx, recipe in enumerate(menu.recipes)}

    for day_index, day in enumerate(menu.days_plan):
        for meal_index, meal in enumerate(day.meals):
            if meal.meal_id:
                meal_refs_by_id[meal.meal_id] = (day_index, meal_index, meal)

    for day_index, day in enumerate(menu.days_plan):
        for meal_index, meal in enumerate(day.meals):
            path = f"days_plan[{day_index}].meals[{meal_index}]"
            recipe, resolve_code = resolve_recipe_for_meal(
                meal,
                menu.recipes,
                path=path,
            )
            if recipe is None or resolve_code in {"MEAL_RECIPE_MISSING", "MEAL_RECIPE_AMBIGUOUS"}:
                continue

            has_from_source = False
            from_source_count = 0

            for ing_index, ingredient in enumerate(recipe.ingredients):
                ing_path = f"recipes[{recipe.name}].ingredients[{ing_index}]"
                raw = ingredient.contribution

                if raw is not None and raw not in VALID_CONTRIBUTIONS:
                    _log_contribution_diagnostic(
                        reason=CONTRIBUTION_REASON_NOT_ALLOWLISTED,
                        recipe_index=recipe_index_by_identity.get(id(recipe), -1),
                        ingredient_index=ing_index,
                        ingredient_name=ingredient.name,
                        contribution_state=type(raw).__name__,
                    )
                    issues.append(
                        ValidationIssue(
                            code="INGREDIENT_CONTRIBUTION_INVALID",
                            message=f"Invalid contribution '{raw}'",
                            path=ing_path,
                            severity="error" if strategy_aware else "warning",
                            reason_code=CONTRIBUTION_REASON_NOT_ALLOWLISTED,
                        )
                    )
                    continue

                if raw == "pantry" and normalize_pantry_contribution(ingredient) == "purchase":
                    _log_contribution_diagnostic(
                        reason=CONTRIBUTION_REASON_PANTRY_MISMATCH,
                        recipe_index=recipe_index_by_identity.get(id(recipe), -1),
                        ingredient_index=ing_index,
                        ingredient_name=ingredient.name,
                        contribution_state="pantry",
                    )
                    issues.append(
                        ValidationIssue(
                            code="INGREDIENT_CONTRIBUTION_INVALID",
                            message=(
                                f"Ingredient '{ingredient.name}' cannot be pantry: "
                                "pantry is allowed only for базовый запас "
                                "(соль, вода, перец, масло, специи); "
                                "use contribution='purchase' for named spices and other products"
                            ),
                            path=ing_path,
                            severity="error" if strategy_aware else "warning",
                            reason_code=CONTRIBUTION_REASON_PANTRY_MISMATCH,
                        )
                    )

                if raw == "from_source":
                    from_source_count += 1
                    has_from_source = True
                    if not meal.uses_leftovers:
                        issues.append(
                            ValidationIssue(
                                code="INGREDIENT_FROM_SOURCE_ON_NON_LEFTOVER",
                                message="from_source only allowed on leftover meals",
                                path=ing_path,
                                severity="error",
                            )
                        )
                    elif not meal.source_meal_id:
                        issues.append(
                            ValidationIssue(
                                code="INGREDIENT_FROM_SOURCE_WITHOUT_SOURCE_MEAL",
                                message="from_source requires source_meal_id",
                                path=ing_path,
                                severity="error",
                            )
                        )
                    elif meal.source_meal_id not in meal_refs_by_id:
                        issues.append(
                            ValidationIssue(
                                code="INGREDIENT_FROM_SOURCE_WITHOUT_SOURCE_MEAL",
                                message=f"source_meal_id '{meal.source_meal_id}' not found",
                                path=path,
                                severity="error",
                            )
                        )
                    else:
                        src_day, _, src_meal = meal_refs_by_id[meal.source_meal_id]
                        if src_day >= day_index:
                            issues.append(
                                ValidationIssue(
                                    code="INGREDIENT_FROM_SOURCE_WITHOUT_SOURCE_MEAL",
                                    message="source meal must be on an earlier day",
                                    path=path,
                                    severity="error",
                                )
                            )

            if strategy_aware and meal.uses_leftovers and recipe.ingredients:
                if not has_from_source:
                    issues.append(
                        ValidationIssue(
                            code="LEFTOVER_SOURCE_INGREDIENT_MISSING",
                            message="Leftover meal must include at least one from_source ingredient",
                            path=path,
                            severity="error",
                        )
                    )

            if strategy_aware and not meal.uses_leftovers and from_source_count > 0:
                if from_source_count == len(recipe.ingredients):
                    issues.append(
                        ValidationIssue(
                            code="INGREDIENT_FROM_SOURCE_ON_NON_LEFTOVER",
                            message="Non-leftover recipe cannot be entirely from_source",
                            path=path,
                            severity="error",
                        )
                    )

    return issues


def validate_recipe_graph(
    menu: MenuPlan,
    *,
    strategy_aware: bool,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    used_recipe_ids: set[str] = set()

    for day_index, day in enumerate(menu.days_plan):
        for meal_index, meal in enumerate(day.meals):
            path = f"days_plan[{day_index}].meals[{meal_index}]"

            if strategy_aware and not meal.recipe_id:
                issues.append(
                    ValidationIssue(
                        code="MEAL_RECIPE_ID_MISSING",
                        message="Strategy-aware meal missing recipe_id",
                        path=path,
                        severity="error",
                    )
                )
                continue

            if meal.recipe_id:
                recipe = find_recipe_by_id(menu.recipes, meal.recipe_id)
                if recipe is None:
                    issues.append(
                        ValidationIssue(
                            code="MEAL_RECIPE_NOT_FOUND",
                            message=f"No recipe for recipe_id '{meal.recipe_id}'",
                            path=path,
                            severity="error",
                        )
                    )
                else:
                    used_recipe_ids.add(meal.recipe_id)
                continue

            _, code = resolve_recipe_for_meal(meal, menu.recipes, path=path)
            if code == "MEAL_RECIPE_AMBIGUOUS":
                issues.append(
                    ValidationIssue(
                        code="MEAL_RECIPE_AMBIGUOUS",
                        message=f"Ambiguous recipe name '{meal.recipe_name}'",
                        path=path,
                        severity="warning" if not strategy_aware else "error",
                    )
                )

    id_counts: dict[str, int] = {}
    for recipe in menu.recipes:
        if not recipe.recipe_id:
            if strategy_aware:
                issues.append(
                    ValidationIssue(
                        code="RECIPE_ID_MISSING",
                        message=f"Recipe '{recipe.name}' missing recipe_id",
                        path="recipes",
                        severity="error",
                    )
                )
            continue
        id_counts[recipe.recipe_id] = id_counts.get(recipe.recipe_id, 0) + 1

    for recipe_id, count in id_counts.items():
        if count > 1:
            issues.append(
                ValidationIssue(
                    code="RECIPE_ID_DUPLICATE",
                    message=f"Duplicate recipe_id '{recipe_id}'",
                    path="recipes",
                    severity="error",
                )
            )

    if strategy_aware:
        for recipe in menu.recipes:
            if recipe.recipe_id and recipe.recipe_id not in used_recipe_ids:
                logger.info("recipe_graph orphan_recipe_id=%s", recipe.recipe_id)

    graph = build_recipe_usage_graph(menu)
    logger.info(
        "recipe_graph recipes=%s unique_ids=%s meals_linked=%s",
        len(menu.recipes),
        len(graph.recipe_id_to_recipe),
        len(graph.meal_id_to_recipe_id),
    )
    return issues
