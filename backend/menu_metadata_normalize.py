"""Deterministic cooking / leftover metadata normalization (Sprint 10.7).

Ownership classification
------------------------
A. Semantic decisions Claude must make
   - uses_leftovers (reuse vs cook fresh)
   - source_meal_id (which earlier meal is the source)
   - requires_cooking (whether this slot cooks)
   - dish / recipe choice, ingredient names and amounts
   - whether a meal is leftover of a given source (intent)

B. Deterministic relational metadata the backend may derive
   - leftover.cooking_instance_id ← source.cooking_instance_id
     when leftover + unique earlier source + source has an instance id
   - leftover.prepared_on_day ← source prepared day / source day index
     when leftover + unique earlier source and source cook day is known
   - requires_cooking.prepared_on_day ← calendar day of the meal
     when the meal sits on that day and requires cooking
   - leftover ingredient.contribution = from_source for ingredients whose
     names uniquely match source-recipe ingredients (no new ingredients)

C. Ambiguous — must remain validation failures
   - missing / unknown source_meal_id
   - source not on an earlier day
   - multiple plausible sources
   - no name-matched ingredients to reclassify as from_source
   - inventing quantities or new ingredient rows

Validators stay strict; normalization only aligns unambiguous relational fields.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from menu_models import DayMeal, MenuPlan, Recipe, normalize_meal_name
from recipe_identity import find_recipe_by_id, resolve_recipe_for_meal

logger = logging.getLogger(__name__)


@dataclass
class MetadataNormalizationStats:
    cooking_normalized: int = 0
    cooking_ambiguous: int = 0
    leftover_normalized: int = 0
    leftover_ambiguous: int = 0
    details: list[dict[str, object]] = field(default_factory=list)


def _resolve_recipe(menu: MenuPlan, meal: DayMeal) -> Recipe | None:
    recipe, _code = resolve_recipe_for_meal(meal, menu.recipes, path="normalize")
    if recipe is not None:
        return recipe
    if meal.recipe_id:
        return find_recipe_by_id(menu.recipes, meal.recipe_id)
    return None


def _source_prepared_day(source: DayMeal, source_day_index: int) -> int | None:
    if source.prepared_on_day is not None:
        return source.prepared_on_day
    if source.requires_cooking:
        return source_day_index + 1
    return None


def normalize_cooking_leftover_metadata(
    menu: MenuPlan,
    *,
    request_id: str | None = None,
) -> tuple[MenuPlan, MetadataNormalizationStats]:
    """Normalize unambiguous cooking/leftover relational fields in-place copy."""
    stats = MetadataNormalizationStats()
    days_plan = [day.model_copy(deep=True) for day in menu.days_plan]
    updated = menu.model_copy(update={"days_plan": days_plan})

    def lookup(meal_id: str) -> tuple[int, DayMeal] | None:
        for day_index, day in enumerate(updated.days_plan):
            for meal in day.meals:
                if meal.meal_id == meal_id:
                    return day_index, meal
        return None

    for day_index, day in enumerate(updated.days_plan):
        day_num = day_index + 1
        for meal_index, meal in enumerate(day.meals):
            updates: dict[str, object] = {}
            normalized_fields: list[str] = []

            # B: cooking meal prepared_on_day must match the day it sits on.
            if meal.requires_cooking and meal.prepared_on_day is not None:
                if meal.prepared_on_day != day_num:
                    updates["prepared_on_day"] = day_num
                    normalized_fields.append("prepared_on_day")

            if meal.uses_leftovers:
                source_id = meal.source_meal_id
                source_ref = lookup(source_id) if source_id else None
                if not source_id or source_ref is None:
                    stats.cooking_ambiguous += 1
                    logger.info(
                        "cooking_metadata_ambiguous request_id=%s meal_id=%s reason=missing_source",
                        request_id,
                        meal.meal_id,
                    )
                    logger.info(
                        "leftover_metadata_ambiguous request_id=%s meal_id=%s reason=missing_source",
                        request_id,
                        meal.meal_id,
                    )
                else:
                    source_day, source_meal = source_ref
                    if source_day >= day_index:
                        stats.cooking_ambiguous += 1
                        logger.info(
                            "cooking_metadata_ambiguous request_id=%s meal_id=%s "
                            "source_meal_id=%s reason=source_not_earlier",
                            request_id,
                            meal.meal_id,
                            source_id,
                        )
                    else:
                        # B: align cooking_instance_id with source.
                        expected_instance = source_meal.cooking_instance_id
                        if expected_instance and meal.cooking_instance_id != expected_instance:
                            updates["cooking_instance_id"] = expected_instance
                            normalized_fields.append("cooking_instance_id")

                        # B: leftover prepared_on_day is when the source was cooked.
                        expected_prepared = _source_prepared_day(source_meal, source_day)
                        if (
                            expected_prepared is not None
                            and meal.prepared_on_day != expected_prepared
                        ):
                            updates["prepared_on_day"] = expected_prepared
                            normalized_fields.append("prepared_on_day")

            if updates:
                day.meals[meal_index] = meal.model_copy(update=updates)
                meal = day.meals[meal_index]
                stats.cooking_normalized += 1
                detail = {
                    "meal_id": meal.meal_id,
                    "source_meal_id": meal.source_meal_id,
                    "normalized_fields": list(normalized_fields),
                }
                stats.details.append(detail)
                logger.info(
                    "cooking_metadata_normalized request_id=%s meal_id=%s "
                    "source_meal_id=%s normalized_fields=%s",
                    request_id,
                    meal.meal_id,
                    meal.source_meal_id,
                    normalized_fields,
                )

    # Ingredient from_source linkage (after meal metadata updates).
    recipe_updates: dict[str, Recipe] = {}

    for day_index, day in enumerate(updated.days_plan):
        for meal in day.meals:
            if not meal.uses_leftovers:
                continue
            source_id = meal.source_meal_id
            source_ref = lookup(source_id) if source_id else None
            if source_ref is None:
                continue
            source_day, source_meal = source_ref
            if source_day >= day_index:
                continue

            leftover_recipe = _resolve_recipe(updated, meal)
            source_recipe = _resolve_recipe(updated, source_meal)
            if leftover_recipe is None or source_recipe is None:
                stats.leftover_ambiguous += 1
                logger.info(
                    "leftover_metadata_ambiguous request_id=%s meal_id=%s "
                    "source_meal_id=%s reason=recipe_unresolved",
                    request_id,
                    meal.meal_id,
                    source_id,
                )
                continue

            if any(ing.contribution == "from_source" for ing in leftover_recipe.ingredients):
                continue

            source_names = {
                normalize_meal_name(ing.name)
                for ing in source_recipe.ingredients
                if ing.name and ing.contribution != "pantry"
            }
            if not source_names:
                source_names = {
                    normalize_meal_name(ing.name)
                    for ing in source_recipe.ingredients
                    if ing.name
                }

            match_indices = [
                idx
                for idx, ing in enumerate(leftover_recipe.ingredients)
                if normalize_meal_name(ing.name) in source_names
                and ing.contribution != "pantry"
            ]

            if not match_indices:
                stats.leftover_ambiguous += 1
                logger.info(
                    "leftover_metadata_ambiguous request_id=%s meal_id=%s "
                    "source_meal_id=%s reason=no_name_match",
                    request_id,
                    meal.meal_id,
                    source_id,
                )
                continue

            # Reclassify matched ingredients only (keep amounts/names).
            key = leftover_recipe.recipe_id or leftover_recipe.name
            base = recipe_updates.get(key, leftover_recipe)
            new_ingredients = list(base.ingredients)
            for idx in match_indices:
                ing = new_ingredients[idx]
                if ing.contribution == "from_source":
                    continue
                new_ingredients[idx] = ing.model_copy(update={"contribution": "from_source"})
            recipe_updates[key] = base.model_copy(update={"ingredients": new_ingredients})
            stats.leftover_normalized += 1
            logger.info(
                "leftover_metadata_normalized request_id=%s meal_id=%s "
                "source_meal_id=%s normalized_fields=%s matched_count=%s",
                request_id,
                meal.meal_id,
                source_id,
                ["ingredient.contribution"],
                len(match_indices),
            )
            stats.details.append(
                {
                    "meal_id": meal.meal_id,
                    "source_meal_id": source_id,
                    "normalized_fields": ["ingredient.contribution"],
                    "matched_count": len(match_indices),
                }
            )

    if recipe_updates:
        new_recipes: list[Recipe] = []
        for recipe in updated.recipes:
            key = recipe.recipe_id or recipe.name
            new_recipes.append(recipe_updates.get(key, recipe))
        updated = updated.model_copy(update={"recipes": new_recipes})

    return updated, stats
