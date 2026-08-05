"""Catalog planner → MenuPlan generation service (no Claude)."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any

from menu_generation.errors import CatalogGenerationError
from menu_generation.finalize import PLANNER_VERSION, finalize_catalog_menu_plan
from menu_generation.menuplan_adapter import WeeklyRecipePlanToMenuPlanAdapter
from menu_validation import MenuValidationRequest
from recipes.enums import ProteinSourceTag, RecipeStatus
from recipes.planning.context import build_planning_context_from_strategy
from recipes.planning.models import PlanStatus
from recipes.planning.planner import WeeklyRecipePlanner
from recipes.planning.weights import WeeklyPlannerConfig
from recipes.quality.enums import QualityStatus
from recipes.repository import RecipeRepository
from recipes.selection.ingredient_resolve import resolve_product_names
from recipes.selection.profile_adapter import PROFILE_PROTEIN_TO_TAG
from strategy.models import WeeklyStrategy

logger = logging.getLogger(__name__)

GenerationProgressCallback = Callable[..., Awaitable[None]]

# Allergy / product text → protein exclusion heuristics.
_ALLERGY_TO_PROTEIN: dict[str, ProteinSourceTag] = {
    "рыба": ProteinSourceTag.FISH,
    "рыб": ProteinSourceTag.FISH,
    "морепродукт": ProteinSourceTag.FISH,
    "курица": ProteinSourceTag.CHICKEN,
    "куриц": ProteinSourceTag.CHICKEN,
    "говядин": ProteinSourceTag.BEEF,
    "свинин": ProteinSourceTag.PORK,
    "индейк": ProteinSourceTag.TURKEY,
    "яйц": ProteinSourceTag.EGGS,
    "яйцо": ProteinSourceTag.EGGS,
}


async def _emit_progress(
    callback: GenerationProgressCallback | None,
    *,
    stage: str,
    attempt: int | None = None,
    max_attempts: int | None = None,
) -> None:
    if callback is None:
        return
    try:
        await callback(stage=stage, attempt=attempt, max_attempts=max_attempts)
    except Exception:
        logger.warning(
            "catalog_generation_progress_callback_failed stage=%s",
            stage,
            exc_info=True,
        )


def _parse_excluded_proteins(allergies: str) -> set[ProteinSourceTag]:
    excluded: set[ProteinSourceTag] = set()
    if not allergies or allergies.strip().lower() in {"", "нет", "none"}:
        return excluded
    for part in allergies.split(","):
        token = part.strip().lower().replace("ё", "е")
        if not token or token in {"нет", "none"}:
            continue
        mapped = PROFILE_PROTEIN_TO_TAG.get(token)
        if mapped:
            excluded.add(mapped)
            continue
        for key, tag in _ALLERGY_TO_PROTEIN.items():
            if key in token:
                excluded.add(tag)
    return excluded


class CatalogMenuGenerationService:
    """Deterministic weekly menu generation via WeeklyRecipePlanner."""

    def __init__(
        self,
        *,
        db_path: Path | str | None = None,
        repository: RecipeRepository | None = None,
        adapter: WeeklyRecipePlanToMenuPlanAdapter | None = None,
        planner: WeeklyRecipePlanner | None = None,
    ) -> None:
        self._repository = repository or RecipeRepository(db_path)
        self._adapter = adapter or WeeklyRecipePlanToMenuPlanAdapter(
            repository=self._repository
        )
        self._planner = planner or WeeklyRecipePlanner(repository=self._repository)

    async def generate(
        self,
        *,
        strategy: WeeklyStrategy,
        persons: int,
        proteins: list | None = None,
        cooktime: str = "medium",
        allergies: str = "нет",
        store: str = "any",
        user_id: int | None = None,
        plan_start_date: date | None = None,
        progress_callback: GenerationProgressCallback | None = None,
        minimum_quality_status: QualityStatus | None = None,
        strategy_id: str | None = None,
    ) -> dict[str, Any]:
        del proteins, store  # Strategy preferred_proteins / store handled via context.
        request_id = str(uuid.uuid4())
        started_at = time.monotonic()
        resolved_start = plan_start_date or date.today()

        await _emit_progress(progress_callback, stage="preparing")

        excluded_proteins = _parse_excluded_proteins(allergies)
        excluded_ingredient_ids: set[str] = set()
        exclusion_names = list(strategy.excluded_products) + list(
            strategy.availability_avoid_products
        )
        if allergies and allergies.strip().lower() not in {"", "нет", "none"}:
            for part in allergies.split(","):
                part = part.strip()
                if part and part.lower() not in {"нет", "none"}:
                    exclusion_names.append(part)
        if exclusion_names:
            ingredients = await self._repository.list_ingredients()
            resolved = resolve_product_names(exclusion_names, ingredients)
            excluded_ingredient_ids = resolved.resolved_ids

        # CRITICAL: allow_cook_day_miss=False for strategy cooking compliance.
        # Keep beam_width=8, pool=15, max_states=4000 unchanged.
        planner_config = WeeklyPlannerConfig(allow_cook_day_miss=False)

        context = build_planning_context_from_strategy(
            strategy,
            excluded_ingredient_ids=excluded_ingredient_ids,
            excluded_protein_sources=excluded_proteins,
            minimum_quality_status=minimum_quality_status,
            config=planner_config,
            strategy_id=strategy_id,
        )

        await _emit_progress(progress_callback, stage="generating")
        weekly_plan = await self._planner.plan(context)

        if weekly_plan.status == PlanStatus.NO_PLAN:
            raise CatalogGenerationError(
                "Catalog planner could not produce a weekly plan",
                code=CatalogGenerationError.PLANNER_NO_PLAN,
                details={
                    "diagnostics": weekly_plan.diagnostics.model_dump(),
                    "violations": list(weekly_plan.violations),
                    "warnings": list(weekly_plan.warnings),
                    "unfilled_slots": list(weekly_plan.diagnostics.unfilled_slots),
                },
            )
        if weekly_plan.status == PlanStatus.PARTIAL:
            raise CatalogGenerationError(
                "Catalog planner produced a partial plan",
                code=CatalogGenerationError.PLANNER_PARTIAL_PLAN,
                details={
                    "diagnostics": weekly_plan.diagnostics.model_dump(),
                    "violations": list(weekly_plan.violations),
                    "meal_count": len(weekly_plan.meals),
                    "unfilled_slots": list(weekly_plan.diagnostics.unfilled_slots),
                },
            )

        await _emit_progress(progress_callback, stage="validating")
        try:
            menu_plan = await self._adapter.adapt(
                weekly_plan,
                strategy=strategy,
                persons=persons,
                plan_start_date=resolved_start,
                strategy_id=strategy_id,
            )
        except CatalogGenerationError:
            raise
        except Exception as exc:
            logger.exception(
                "catalog_menuplan_adapter_failed request_id=%s", request_id
            )
            raise CatalogGenerationError(
                "MenuPlan adapter failed",
                code=CatalogGenerationError.MENUPLAN_ADAPTER_FAILED,
                details={"error_type": type(exc).__name__},
            ) from exc

        catalog_count = await self._repository.count_recipes(status=RecipeStatus.ACTIVE)
        meal_count = len(weekly_plan.meals)
        leftover_count = sum(1 for m in weekly_plan.meals if m.is_leftover)
        cooking_instance_count = len(weekly_plan.cooking_instances)
        unique_recipe_count = len({m.recipe_id for m in weekly_plan.meals})

        validation_request = MenuValidationRequest(
            days=strategy.days,
            budget=float(strategy.budget),
            meal_types=list(strategy.meal_types),
            meals_per_day=strategy.meals_per_day,
            persons=persons,
            cooktime=cooktime,
            allergies=allergies,
            strategy_aware=True,
        )

        await _emit_progress(progress_callback, stage="validating")
        payload = finalize_catalog_menu_plan(
            menu_plan,
            request=validation_request,
            strategy=strategy,
            planner_score=float(weekly_plan.score),
            planning_duration_ms=float(
                weekly_plan.diagnostics.planning_duration_ms or 0.0
            ),
            catalog_recipe_count=int(catalog_count) if catalog_count else 80,
            meal_count=meal_count,
            leftover_count=leftover_count,
            cooking_instance_count=cooking_instance_count,
            unique_recipe_count=unique_recipe_count,
            request_id=request_id,
        )

        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            "catalog_menu_generated request_id=%s user_id=%s engine=catalog_planner "
            "planner_version=%s planner_score=%s planning_duration_ms=%s "
            "catalog_recipe_count=%s meal_count=%s leftover_count=%s "
            "cooking_instance_count=%s unique_recipe_count=%s duration_ms=%s",
            request_id,
            user_id,
            PLANNER_VERSION,
            weekly_plan.score,
            weekly_plan.diagnostics.planning_duration_ms,
            catalog_count,
            meal_count,
            leftover_count,
            cooking_instance_count,
            unique_recipe_count,
            duration_ms,
        )
        return payload
