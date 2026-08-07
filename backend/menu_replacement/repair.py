"""Apply catalog recipe replacement onto a MenuPlan (copy-on-write)."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from enum import StrEnum

from cooking_identity import default_cooking_instance_id_for_meal
from menu_generation.menuplan_adapter import (
    leftover_menu_recipe_id,
    WeeklyRecipePlanToMenuPlanAdapter,
)
from menu_models import DayMeal, MenuPlan, Recipe as MenuRecipe
from recipe_identity import is_recipe_id_referenced
from recipes.models import Recipe as CatalogRecipe
from shopping.basket_builder import build_basket_from_menu
from shopping.exceptions import BasketPriceUnavailableError
from strategy.replacement_context import ReplacementContext
from strategy.replacement_exceptions import ReplacementPriceResolutionError


_LEFTOVER_SUFFIX = "__leftover"


class RepairMode(StrEnum):
    SINGLE_SLOT = "single_slot"
    SOURCE_CHAIN = "source_chain"
    LEFTOVER_TO_INDEPENDENT = "leftover_to_independent"


@dataclass(frozen=True)
class RepairResult:
    menu_plan: MenuPlan
    changed_meal_ids: list[str]
    mode: RepairMode
    old_catalog_recipe_id: str | None
    new_catalog_recipe_id: str


def catalog_id_from_menu_recipe_id(recipe_id: str | None) -> str | None:
    if not recipe_id:
        return None
    if recipe_id.endswith(_LEFTOVER_SUFFIX):
        return recipe_id[: -len(_LEFTOVER_SUFFIX)]
    return recipe_id


def count_leftovers_in_menu(menu: MenuPlan) -> int:
    return sum(1 for day in menu.days_plan for meal in day.meals if meal.uses_leftovers)


def collect_downstream(menu: MenuPlan, source_meal_id: str) -> list[DayMeal]:
    return [
        meal
        for day in menu.days_plan
        for meal in day.meals
        if meal.source_meal_id == source_meal_id
    ]


def find_meal(menu: MenuPlan, meal_id: str) -> DayMeal | None:
    for day in menu.days_plan:
        for meal in day.meals:
            if meal.meal_id == meal_id:
                return meal
    return None


def day_number_for(menu: MenuPlan, meal_id: str) -> int | None:
    for idx, day in enumerate(menu.days_plan):
        for meal in day.meals:
            if meal.meal_id == meal_id:
                return idx + 1
    return None


def _upsert_meal(menu: MenuPlan, meal_id: str, new_meal: DayMeal) -> None:
    for day in menu.days_plan:
        for idx, meal in enumerate(day.meals):
            if meal.meal_id == meal_id:
                day.meals[idx] = new_meal
                return
    raise ValueError(f"meal_id not found during repair: {meal_id}")


def _build_snapshots(
    adapter: WeeklyRecipePlanToMenuPlanAdapter,
    catalog: CatalogRecipe,
    *,
    persons: int,
    servings_cooked: int,
    need_leftover: bool,
) -> tuple[MenuRecipe, MenuRecipe | None]:
    cook = adapter._build_snapshot(
        catalog,
        target_servings=float(persons) * float(max(1, servings_cooked)),
        menu_recipe_id=catalog.id,
        is_leftover=False,
    )
    leftover = None
    if need_leftover:
        leftover = adapter._build_snapshot(
            catalog,
            target_servings=float(persons),
            menu_recipe_id=leftover_menu_recipe_id(catalog.id),
            is_leftover=True,
        )
    return cook, leftover


def _finalize_recipes(menu: MenuPlan, new_snaps: list[MenuRecipe]) -> list[MenuRecipe]:
    by_id: dict[str, MenuRecipe] = {
        r.recipe_id: r for r in menu.recipes if r.recipe_id
    }
    for snap in new_snaps:
        if snap.recipe_id:
            by_id[snap.recipe_id] = snap
    # Probe references with full map, then keep only referenced.
    probe = menu.model_copy(update={"recipes": list(by_id.values())})
    return [
        recipe
        for recipe_id, recipe in by_id.items()
        if is_recipe_id_referenced(probe, recipe_id)
    ]


def _rebuild_basket(menu: MenuPlan, context: ReplacementContext) -> MenuPlan:
    try:
        basket_result = build_basket_from_menu(
            menu,
            existing_basket=context.menu_plan.basket,
            require_all_prices=False,
        )
    except BasketPriceUnavailableError as exc:
        raise ReplacementPriceResolutionError(exc.unresolved) from exc
    return menu.model_copy(
        update={
            "basket": basket_result.basket,
            "total_cost": float(basket_result.total_cost or 0),
            "strategy_id": context.menu_plan.strategy_id,
            "plan_start_date": context.menu_plan.plan_start_date,
            "summary": context.menu_plan.summary,
            "generation_engine": context.menu_plan.generation_engine
            or "catalog_planner",
        }
    )


def _unique(ids: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for mid in ids:
        if mid not in seen:
            seen.add(mid)
            out.append(mid)
    return out


def apply_catalog_repair(
    context: ReplacementContext,
    *,
    catalog: CatalogRecipe,
    persons: int,
    mode: RepairMode,
    adapter: WeeklyRecipePlanToMenuPlanAdapter | None = None,
) -> RepairResult:
    adapter = adapter or WeeklyRecipePlanToMenuPlanAdapter()
    menu = deepcopy(context.menu_plan)
    target = context.target.meal_ref.meal
    target_id = target.meal_id
    if not target_id:
        raise ValueError("target meal_id is required")
    old_catalog_id = catalog_id_from_menu_recipe_id(target.recipe_id)
    day_number = context.target.day_number
    changed: list[str] = []

    if mode == RepairMode.SINGLE_SLOT:
        cook_snap, _ = _build_snapshots(
            adapter, catalog, persons=persons, servings_cooked=1, need_leftover=False
        )
        instance_id = target.cooking_instance_id or default_cooking_instance_id_for_meal(
            target
        )
        _upsert_meal(
            menu,
            target_id,
            target.model_copy(
                update={
                    "recipe_name": catalog.name,
                    "recipe_id": catalog.id,
                    "requires_cooking": bool(catalog.requires_cooking),
                    "uses_leftovers": False,
                    "source_meal_id": None,
                    "prepared_on_day": day_number,
                    "cooking_instance_id": instance_id,
                }
            ),
        )
        changed.append(target_id)
        menu = menu.model_copy(
            update={"recipes": _finalize_recipes(menu, [cook_snap])}
        )

    elif mode == RepairMode.LEFTOVER_TO_INDEPENDENT:
        cook_snap, _ = _build_snapshots(
            adapter, catalog, persons=persons, servings_cooked=1, need_leftover=False
        )
        new_instance = default_cooking_instance_id_for_meal(target)
        _upsert_meal(
            menu,
            target_id,
            target.model_copy(
                update={
                    "recipe_name": catalog.name,
                    "recipe_id": catalog.id,
                    "requires_cooking": bool(catalog.requires_cooking),
                    "uses_leftovers": False,
                    "source_meal_id": None,
                    "prepared_on_day": day_number,
                    "cooking_instance_id": new_instance,
                }
            ),
        )
        changed.append(target_id)

        # Shrink former source cook snapshot when no dependents remain.
        extra_snaps: list[MenuRecipe] = [cook_snap]
        source_id = target.source_meal_id
        if source_id:
            remaining = [
                m for m in collect_downstream(menu, source_id) if m.meal_id != target_id
            ]
            source_meal = find_meal(menu, source_id)
            if source_meal is not None and not remaining:
                src_cat_id = catalog_id_from_menu_recipe_id(source_meal.recipe_id)
                # Re-point source instance to single-serving if we still have cook snap.
                src_snap = next(
                    (r for r in menu.recipes if r.recipe_id == source_meal.recipe_id),
                    None,
                )
                if src_snap is not None and src_cat_id == source_meal.recipe_id:
                    # Leave existing cook snapshot; basket instance-dedupe already
                    # charges once per cooking_instance_id. No orphan leftover remains.
                    pass

        menu = menu.model_copy(
            update={"recipes": _finalize_recipes(menu, extra_snaps)}
        )

    elif mode == RepairMode.SOURCE_CHAIN:
        # Resolve source meal + dependents (target may be leftover or cook source).
        if target.uses_leftovers and target.source_meal_id:
            source_id = target.source_meal_id
            source_meal = find_meal(menu, source_id)
            if source_meal is None:
                raise ValueError("leftover source missing")
            dep_meals = collect_downstream(menu, source_id)
            source_day = day_number_for(menu, source_id) or day_number
        else:
            source_id = target_id
            source_meal = target
            dep_meals = [ref.meal for ref in context.target.downstream_refs]
            source_day = day_number

        servings = 1 + len(dep_meals)
        instance_id = (
            source_meal.cooking_instance_id
            or default_cooking_instance_id_for_meal(source_meal)
        )
        cook_snap, leftover_snap = _build_snapshots(
            adapter,
            catalog,
            persons=persons,
            servings_cooked=servings,
            need_leftover=bool(dep_meals),
        )
        snaps = [cook_snap]
        if leftover_snap is not None:
            snaps.append(leftover_snap)

        _upsert_meal(
            menu,
            source_id,
            source_meal.model_copy(
                update={
                    "recipe_name": catalog.name,
                    "recipe_id": catalog.id,
                    "requires_cooking": bool(catalog.requires_cooking),
                    "uses_leftovers": False,
                    "source_meal_id": None,
                    "prepared_on_day": source_day,
                    "cooking_instance_id": instance_id,
                }
            ),
        )
        changed.append(source_id)

        for dep in dep_meals:
            if not dep.meal_id:
                continue
            _upsert_meal(
                menu,
                dep.meal_id,
                dep.model_copy(
                    update={
                        "recipe_name": catalog.name,
                        "recipe_id": leftover_menu_recipe_id(catalog.id),
                        "requires_cooking": False,
                        "uses_leftovers": True,
                        "source_meal_id": source_id,
                        "prepared_on_day": source_day,
                        "cooking_instance_id": instance_id,
                    }
                ),
            )
            changed.append(dep.meal_id)

        menu = menu.model_copy(update={"recipes": _finalize_recipes(menu, snaps)})
    else:
        raise ValueError(f"unknown repair mode: {mode}")

    menu = _rebuild_basket(menu, context)
    return RepairResult(
        menu_plan=menu,
        changed_meal_ids=_unique(changed),
        mode=mode,
        old_catalog_recipe_id=old_catalog_id,
        new_catalog_recipe_id=catalog.id,
    )
