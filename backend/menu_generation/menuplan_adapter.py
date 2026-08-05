"""Adapt WeeklyRecipePlan → MenuPlan (no Claude, no basket rebuild)."""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date
from decimal import Decimal

from menu_generation.errors import CatalogGenerationError
from menu_models import (
    DayMeal,
    DayPlan,
    MenuPlan,
    Recipe as MenuRecipe,
    RecipeIngredient as MenuIngredient,
)
from menu_validation import PANTRY_STAPLES
from recipes.models import Recipe as CatalogRecipe
from recipes.planning.models import WeeklyRecipePlan
from recipes.repository import RecipeRepository
from recipes.scaler import RecipeScaleError, RecipeScaler
from strategy.models import WeeklyStrategy

logger = logging.getLogger(__name__)

# Leftover meals need a distinct MenuPlan recipe_id so from_source contributions
# do not leak onto the cook snapshot (MenuPlan contribution contract).
_LEFTOVER_RECIPE_SUFFIX = "__leftover"


def meal_id_for_slot(slot_id: str) -> str:
    return f"meal_{slot_id}"


def leftover_menu_recipe_id(catalog_recipe_id: str) -> str:
    return f"{catalog_recipe_id}{_LEFTOVER_RECIPE_SUFFIX}"


def _format_amount(quantity: Decimal, unit: str, display_name: str | None = None) -> str:
    q = quantity
    if q == q.to_integral_value():
        qty_str = str(int(q))
    else:
        qty_str = format(q.normalize(), "f").rstrip("0").rstrip(".")
    unit_label = {
        "g": "г",
        "ml": "мл",
        "piece": "шт",
        "pcs": "шт",
        "tsp": "ч.л.",
        "tbsp": "ст.л.",
    }.get(unit, unit)
    return f"{qty_str} {unit_label}".strip()


def _kbju_string(recipe: CatalogRecipe) -> str:
    cal = getattr(recipe, "calories_per_100g", None)
    protein = getattr(recipe, "protein_g_per_100g", None)
    fat = getattr(recipe, "fat_g_per_100g", None)
    carbs = getattr(recipe, "carbs_g_per_100g", None)
    if cal is None and protein is None:
        return ""
    parts: list[str] = []
    if cal is not None:
        parts.append(f"~{int(round(cal))} ккал/100г")
    macros = []
    if protein is not None:
        macros.append(f"Б {protein:.0f}")
    if fat is not None:
        macros.append(f"Ж {fat:.0f}")
    if carbs is not None:
        macros.append(f"У {carbs:.0f}")
    if macros:
        parts.append(" · ".join(macros))
    return " · ".join(parts)


def _contribution_for_ingredient(display_name: str, *, is_leftover: bool) -> str:
    canonical = display_name.strip().lower().replace("ё", "е")
    if canonical in PANTRY_STAPLES or any(s in canonical for s in PANTRY_STAPLES):
        return "pantry"
    if is_leftover:
        return "from_source"
    return "purchase"


class WeeklyRecipePlanToMenuPlanAdapter:
    def __init__(
        self,
        repository: RecipeRepository | None = None,
        scaler: RecipeScaler | None = None,
    ) -> None:
        self._repository = repository or RecipeRepository()
        self._scaler = scaler or RecipeScaler()

    async def adapt(
        self,
        weekly_plan: WeeklyRecipePlan,
        *,
        strategy: WeeklyStrategy,
        persons: int,
        plan_start_date: date,
        strategy_id: str | None = None,
    ) -> MenuPlan:
        if persons < 1:
            raise CatalogGenerationError(
                "persons must be >= 1",
                code=CatalogGenerationError.MENUPLAN_ADAPTER_FAILED,
                details={"persons": persons},
            )

        servings_by_instance = {
            ci.cooking_instance_id: int(ci.servings_cooked)
            for ci in weekly_plan.cooking_instances
        }
        recipe_ids = {m.recipe_id for m in weekly_plan.meals}
        catalog_by_id: dict[str, CatalogRecipe] = {}
        for rid in recipe_ids:
            recipe = await self._repository.get_recipe_with_dependencies(rid)
            if recipe is None:
                raise CatalogGenerationError(
                    f"Catalog recipe not found: {rid}",
                    code=CatalogGenerationError.CATALOG_RECIPE_NOT_FOUND,
                    details={"recipe_id": rid},
                )
            catalog_by_id[rid] = recipe

        # Target servings per catalog recipe_id (max across cooking instances).
        target_servings_by_recipe: dict[str, float] = {}
        for meal in weekly_plan.meals:
            if meal.is_leftover:
                continue
            cooked = servings_by_instance.get(meal.cooking_instance_id, 1)
            target = float(persons) * float(cooked)
            prev = target_servings_by_recipe.get(meal.recipe_id, 0.0)
            if target > prev:
                target_servings_by_recipe[meal.recipe_id] = target
        for rid in recipe_ids:
            if rid not in target_servings_by_recipe:
                target_servings_by_recipe[rid] = float(persons)

        cook_snapshots: dict[str, MenuRecipe] = {}
        leftover_needed: set[str] = set()
        for meal in weekly_plan.meals:
            if meal.is_leftover:
                leftover_needed.add(meal.recipe_id)

        for rid, catalog in catalog_by_id.items():
            cook_snapshots[rid] = self._build_snapshot(
                catalog,
                target_servings=target_servings_by_recipe[rid],
                menu_recipe_id=rid,
                is_leftover=False,
            )
            if rid in leftover_needed:
                leftover_id = leftover_menu_recipe_id(rid)
                cook_snapshots[leftover_id] = self._build_snapshot(
                    catalog,
                    target_servings=float(persons),
                    menu_recipe_id=leftover_id,
                    is_leftover=True,
                )

        by_day: dict[int, list[DayMeal]] = defaultdict(list)
        for meal in weekly_plan.meals:
            mid = meal_id_for_slot(meal.slot_id)
            if meal.is_leftover:
                source_slot = meal.source_slot_id
                if not source_slot:
                    raise CatalogGenerationError(
                        f"Leftover meal missing source_slot_id: {meal.slot_id}",
                        code=CatalogGenerationError.MENUPLAN_ADAPTER_FAILED,
                        details={"slot_id": meal.slot_id},
                    )
                source_meal = next(
                    (m for m in weekly_plan.meals if m.slot_id == source_slot),
                    None,
                )
                prepared = source_meal.day_index if source_meal else meal.day_index
                by_day[meal.day_index].append(
                    DayMeal(
                        type=meal.meal_type,  # type: ignore[arg-type]
                        recipe_name=meal.recipe_name or catalog_by_id[meal.recipe_id].name,
                        recipe_id=leftover_menu_recipe_id(meal.recipe_id),
                        meal_id=mid,
                        requires_cooking=False,
                        uses_leftovers=True,
                        source_meal_id=meal_id_for_slot(source_slot),
                        prepared_on_day=prepared,
                        cooking_instance_id=meal.cooking_instance_id,
                    )
                )
            else:
                catalog = catalog_by_id[meal.recipe_id]
                # Planner marks cook-actions as requires_cooking=True even for
                # no-cook catalog recipes (allowed on non-cook days). Prefer catalog.
                requires_cooking = bool(catalog.requires_cooking)
                by_day[meal.day_index].append(
                    DayMeal(
                        type=meal.meal_type,  # type: ignore[arg-type]
                        recipe_name=meal.recipe_name or catalog.name,
                        recipe_id=meal.recipe_id,
                        meal_id=mid,
                        requires_cooking=requires_cooking,
                        uses_leftovers=False,
                        source_meal_id=None,
                        prepared_on_day=meal.day_index,
                        cooking_instance_id=meal.cooking_instance_id,
                    )
                )

        days_plan: list[DayPlan] = []
        for day_index in sorted(by_day.keys()):
            days_plan.append(
                DayPlan(
                    day=f"День {day_index}",
                    meals=by_day[day_index],
                )
            )

        recipes = list(cook_snapshots.values())
        if not recipes or not days_plan:
            raise CatalogGenerationError(
                "Adapter produced empty menu",
                code=CatalogGenerationError.MENUPLAN_ADAPTER_FAILED,
                details={
                    "recipe_count": len(recipes),
                    "day_count": len(days_plan),
                },
            )

        # Basket rebuilt in finalize; construct bypasses non-empty basket validator.
        return MenuPlan.model_construct(
            summary=f"Меню на {weekly_plan.days} дней (catalog planner)",
            plan_start_date=plan_start_date,
            strategy_id=strategy_id,
            total_cost=0.0,
            days_plan=days_plan,
            recipes=recipes,
            basket=[],
            generation_engine="catalog_planner",
            planner_score=float(weekly_plan.score),
            planner_version="10.10",
            planning_duration_ms=float(
                weekly_plan.diagnostics.planning_duration_ms or 0.0
            ),
        )

    def _build_snapshot(
        self,
        catalog: CatalogRecipe,
        *,
        target_servings: float,
        menu_recipe_id: str,
        is_leftover: bool,
    ) -> MenuRecipe:
        try:
            scaled = self._scaler.scale(catalog, target_servings)
        except RecipeScaleError:
            # Clamp into allowed batch window when LIMITED, else fall back to base.
            try:
                lo = float(catalog.min_batch_servings)
                hi = float(catalog.max_batch_servings)
                clamped = min(max(target_servings, lo), hi)
                scaled = self._scaler.scale(catalog, clamped)
            except RecipeScaleError:
                scaled = self._scaler.scale(catalog, float(catalog.base_servings))

        by_id = {i.id: i for i in catalog.ingredients}
        ingredients: list[MenuIngredient] = []
        for item in scaled.ingredients:
            base = by_id.get(item.recipe_ingredient_id)
            display = item.display_name
            if display is None and base is not None and base.ingredient is not None:
                display = base.ingredient.display_name
            if display is None and base is not None:
                display = base.ingredient_id
            if not display:
                display = item.ingredient_id
            unit = item.unit.value if hasattr(item.unit, "value") else str(item.unit)
            amount = _format_amount(item.quantity, unit, display)
            contribution = _contribution_for_ingredient(display, is_leftover=is_leftover)
            # Leftover snapshots: keep pantry as pantry; mark the first non-pantry
            # as from_source and remaining purchase extras if any were purchase-only.
            ingredients.append(
                MenuIngredient(
                    name=display,
                    amount=amount,
                    contribution=contribution,  # type: ignore[arg-type]
                )
            )

        if is_leftover and ingredients:
            # Ensure at least one from_source for strategy-aware validation.
            if not any(i.contribution == "from_source" for i in ingredients):
                for idx, ing in enumerate(ingredients):
                    if ing.contribution != "pantry":
                        ingredients[idx] = ing.model_copy(
                            update={"contribution": "from_source"}
                        )
                        break
                else:
                    ingredients[0] = ingredients[0].model_copy(
                        update={"contribution": "from_source"}
                    )

        steps = [
            step.instruction.strip()
            for step in sorted(catalog.steps, key=lambda s: s.step_number)
            if step.instruction and step.instruction.strip()
        ]
        if not steps:
            steps = ["Приготовить по рецепту."]

        return MenuRecipe(
            name=catalog.name,
            recipe_id=menu_recipe_id,
            cook_time=f"{catalog.total_time_minutes} мин",
            kbju=_kbju_string(catalog),
            ingredients=ingredients,
            steps=steps,
            difficulty=catalog.difficulty.value if catalog.difficulty else None,
        )
