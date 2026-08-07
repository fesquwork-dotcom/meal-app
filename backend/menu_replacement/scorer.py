"""Local deterministic replacement scoring (does not touch Selector weights)."""

from __future__ import annotations

from dataclasses import dataclass

from menu_models import DayMeal, MenuPlan
from menu_replacement.reasons import CatalogReplacementReason
from recipes.enums import BudgetClass, TagType
from recipes.models import Recipe
from recipes.selection.models import RecipeCandidate


_BUDGET_RANK = {
    BudgetClass.VERY_BUDGET: 0,
    BudgetClass.BUDGET: 1,
    BudgetClass.STANDARD: 2,
    BudgetClass.PREMIUM: 3,
}


@dataclass(frozen=True)
class ScoredReplacement:
    candidate: RecipeCandidate
    total_score: float
    components: dict[str, float]
    machine_reasons: tuple[str, ...]


def _catalog_id(recipe_id: str | None) -> str | None:
    if not recipe_id:
        return None
    if recipe_id.endswith("__leftover"):
        return recipe_id[: -len("__leftover")]
    return recipe_id


def _week_recipe_ids(menu: MenuPlan, *, meal_type: str | None = None) -> set[str]:
    ids: set[str] = set()
    for day in menu.days_plan:
        for meal in day.meals:
            if meal_type and meal.type != meal_type:
                continue
            rid = _catalog_id(meal.recipe_id)
            if rid:
                ids.add(rid)
    return ids


def _protein_tags(recipe: Recipe) -> set[str]:
    return {
        t.tag_value
        for t in recipe.tags
        if t.tag_type == TagType.PROTEIN_SOURCE
    }


def _ingredient_ids(recipe: Recipe) -> set[str]:
    return {i.ingredient_id for i in recipe.ingredients}


def _has_ingredient_name(recipe: Recipe, needle: str) -> bool:
    n = needle.strip().lower().replace("ё", "е")
    if not n:
        return False
    for ing in recipe.ingredients:
        names = [ing.ingredient_id]
        if ing.ingredient is not None:
            names.extend(
                [
                    ing.ingredient.canonical_name,
                    ing.ingredient.display_name,
                    *[a.alias for a in ing.ingredient.aliases],
                ]
            )
        for name in names:
            if n in str(name).lower().replace("ё", "е"):
                return True
    return False


def weekly_reject_reason(
    recipe: Recipe,
    *,
    menu: MenuPlan,
    target: DayMeal,
    day_number: int,
    cook_days: set[int],
    current_catalog_id: str | None,
    force_no_cook: bool,
) -> str | None:
    """Return rejection code if recipe is incompatible with the week, else None."""
    if recipe.id == current_catalog_id:
        return "CURRENT_RECIPE"
    if force_no_cook and recipe.requires_cooking:
        return "REQUIRES_COOKING_ON_NON_COOK_DAY"
    if day_number not in cook_days and recipe.requires_cooking:
        return "REQUIRES_COOKING_ON_NON_COOK_DAY"

    # Avoid consecutive same catalog recipe for same meal type.
    day_idx = day_number - 1
    for offset in (-1, 1):
        other_idx = day_idx + offset
        if other_idx < 0 or other_idx >= len(menu.days_plan):
            continue
        for meal in menu.days_plan[other_idx].meals:
            if meal.meal_id == target.meal_id:
                continue
            if meal.type != target.type:
                continue
            if _catalog_id(meal.recipe_id) == recipe.id:
                return "CONSECUTIVE_SAME_RECIPE"

    return None


def score_replacement_candidate(
    candidate: RecipeCandidate,
    *,
    reason: CatalogReplacementReason,
    menu: MenuPlan,
    target: DayMeal,
    current_recipe: Recipe | None,
    target_ingredient: str | None,
    day_number: int,
    cook_days: set[int],
    force_no_cook: bool,
) -> ScoredReplacement | None:
    recipe = candidate.recipe
    current_id = _catalog_id(target.recipe_id)
    reject = weekly_reject_reason(
        recipe,
        menu=menu,
        target=target,
        day_number=day_number,
        cook_days=cook_days,
        current_catalog_id=current_id,
        force_no_cook=force_no_cook,
    )
    if reject:
        return None

    if reason == CatalogReplacementReason.INGREDIENT_UNAVAILABLE and target_ingredient:
        if _has_ingredient_name(recipe, target_ingredient):
            return None
    if reason == CatalogReplacementReason.DONT_LIKE and target_ingredient:
        if _has_ingredient_name(recipe, target_ingredient):
            return None

    components: dict[str, float] = {
        "selector_score": float(candidate.score),
        "reason_match": 0.0,
        "weekly_compatibility": 1.0,
        "diversity": 0.0,
        "ingredient_reuse": 0.0,
        "minimal_change": 0.0,
    }
    machine: list[str] = ["SAME_MEAL_TYPE", "PROFILE_COMPATIBLE", "WEEKLY_COMPATIBLE"]

    week_ids = _week_recipe_ids(menu)
    if recipe.id not in week_ids:
        components["diversity"] += 0.35
        machine.append("NEW_TO_WEEK")
    elif recipe.id != current_id:
        components["diversity"] += 0.1

    if current_recipe is not None:
        cur_proteins = _protein_tags(current_recipe)
        new_proteins = _protein_tags(recipe)
        if new_proteins and cur_proteins and new_proteins.isdisjoint(cur_proteins):
            components["diversity"] += 0.25
            machine.append("DIFFERENT_PROTEIN")
        shared = len(_ingredient_ids(current_recipe) & _ingredient_ids(recipe))
        total = max(len(_ingredient_ids(current_recipe) | _ingredient_ids(recipe)), 1)
        reuse = shared / total
        components["ingredient_reuse"] = 0.15 * reuse
        # Structural difference for dislike / variety.
        structure_delta = 1.0 - reuse
        if reason in {
            CatalogReplacementReason.DONT_LIKE,
            CatalogReplacementReason.WANT_VARIETY,
        }:
            components["reason_match"] += 0.45 * structure_delta
            if structure_delta >= 0.4:
                machine.append("STRUCTURALLY_DIFFERENT")
        else:
            components["minimal_change"] += 0.2 * reuse

    if reason == CatalogReplacementReason.TOO_LONG and current_recipe is not None:
        if recipe.total_time_minutes < current_recipe.total_time_minutes:
            gain = (
                current_recipe.total_time_minutes - recipe.total_time_minutes
            ) / max(current_recipe.total_time_minutes, 1)
            components["reason_match"] += 0.7 * min(1.0, gain + 0.2)
            machine.append("FASTER_THAN_CURRENT")
        elif recipe.total_time_minutes > current_recipe.total_time_minutes:
            components["reason_match"] -= 0.5

    if reason == CatalogReplacementReason.TOO_EXPENSIVE and current_recipe is not None:
        cur_rank = _BUDGET_RANK.get(current_recipe.budget_class, 1)
        new_rank = _BUDGET_RANK.get(recipe.budget_class, 1)
        if new_rank < cur_rank:
            components["reason_match"] += 0.7
            machine.append("CHEAPER_BUDGET_CLASS")
        elif new_rank > cur_rank:
            components["reason_match"] -= 0.4

    if reason == CatalogReplacementReason.INGREDIENT_UNAVAILABLE:
        components["reason_match"] += 0.5
        machine.append("EXCLUDES_UNAVAILABLE_INGREDIENT")

    if reason == CatalogReplacementReason.WANT_VARIETY:
        components["reason_match"] += 0.2 * components["diversity"]

    if reason == CatalogReplacementReason.DONT_LIKE:
        components["reason_match"] += 0.15

    total = (
        components["selector_score"]
        + components["reason_match"]
        + components["weekly_compatibility"]
        + components["diversity"]
        + components["ingredient_reuse"]
        + components["minimal_change"]
    )
    return ScoredReplacement(
        candidate=candidate,
        total_score=total,
        components=components,
        machine_reasons=tuple(dict.fromkeys(machine)),
    )


def pick_best_scored(scored: list[ScoredReplacement]) -> ScoredReplacement | None:
    if not scored:
        return None
    return sorted(
        scored,
        key=lambda s: (-s.total_score, s.candidate.recipe.id),
    )[0]
