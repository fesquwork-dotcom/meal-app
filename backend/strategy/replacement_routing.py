"""Replacement engine routing for catalog vs legacy Claude menus.

Primary signal: ``MenuPlan.generation_engine`` (request and/or durable DB JSON).
Secondary safety: catalog markers must never fall through to Claude.
"""

from __future__ import annotations

from enum import StrEnum

from menu_generation.engine import GenerationEngine
from menu_models import MenuPlan


class ReplacementEngineChoice(StrEnum):
    CATALOG = "catalog"
    LEGACY = "legacy"


def normalize_generation_engine(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip().lower()
    return stripped or None


def has_catalog_markers(menu_plan: MenuPlan) -> bool:
    """Heuristic safety markers — never the primary routing policy."""
    if normalize_generation_engine(menu_plan.generation_engine) == (
        GenerationEngine.CATALOG_PLANNER.value
    ):
        return True
    if menu_plan.planner_version:
        return True
    if menu_plan.planner_score is not None:
        return True
    if menu_plan.planning_duration_ms is not None:
        return True

    # Catalog adapter meal_ids are ``meal_{slot_id}`` e.g. meal_day2_lunch.
    meal_ids = [
        meal.meal_id
        for day in menu_plan.days_plan
        for meal in day.meals
        if meal.meal_id
    ]
    if meal_ids and all(
        mid.startswith("meal_day") and "_" in mid[len("meal_day") :]
        for mid in meal_ids
    ):
        return True

    # Catalog recipe ids are slug-like; leftover snapshots use __leftover.
    recipe_ids = [
        meal.recipe_id
        for day in menu_plan.days_plan
        for meal in day.meals
        if meal.recipe_id
    ]
    if recipe_ids and any(
        rid.endswith("__leftover") or "-" in rid for rid in recipe_ids
    ):
        # Only treat as catalog marker when cooking instances are also present
        # (legacy Claude plans usually lack cooking_instance_id).
        if any(
            meal.cooking_instance_id
            for day in menu_plan.days_plan
            for meal in day.meals
        ):
            return True
    return False


def resolve_replacement_engine(
    *,
    request_engine: str | None,
    persisted_engine: str | None,
    catalog_marker_present: bool,
) -> ReplacementEngineChoice:
    """Decide catalog vs legacy.

    Rules:
    1. Effective engine = request_engine or persisted_engine.
    2. ``catalog_planner`` → catalog.
    3. Catalog markers without catalog engine → caller must refuse Claude
       (raise routing error); this helper returns CATALOG so callers can
       either route or treat as routing error before Claude.
    4. Otherwise → legacy.
    """
    effective = request_engine or persisted_engine
    if effective == GenerationEngine.CATALOG_PLANNER.value:
        return ReplacementEngineChoice.CATALOG
    if catalog_marker_present and effective != GenerationEngine.LEGACY_CLAUDE.value:
        # Markers imply catalog lineage; never Claude.
        return ReplacementEngineChoice.CATALOG
    return ReplacementEngineChoice.LEGACY
