"""Catalog planner → MenuPlan generation service (no Claude)."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import date
from pathlib import Path
from typing import Any

from menu_generation.cook_day_relaxation import (
    EXTRA_COOK_DAY_EXPLANATION_RU,
    EXTRA_COOK_DAY_REQUIRED,
    build_relaxation_metadata,
    compute_extra_cook_days_from_plan,
    relaxed_planner_config,
    should_attempt_cook_day_relaxation,
    strict_planner_config,
)
from menu_generation.errors import CatalogGenerationError
from menu_generation.finalize import PLANNER_VERSION, finalize_catalog_menu_plan
from menu_generation.menuplan_adapter import WeeklyRecipePlanToMenuPlanAdapter
from menu_validation import MenuValidationRequest
from recipes.enums import ProteinSourceTag, RecipeStatus
from recipes.planning.context import build_planning_context_from_strategy
from recipes.planning.models import PlanStatus, WeeklyRecipePlan
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


def _raise_planner_failure(weekly_plan: WeeklyRecipePlan) -> None:
    planner_diagnostics = weekly_plan.diagnostics.to_dict()
    if weekly_plan.status == PlanStatus.NO_PLAN:
        logger.warning(
            "planner_failed status=no_plan termination=%s failed_slot=%s "
            "visited_states=%s beam_iterations=%s hard_filters=%s",
            weekly_plan.diagnostics.termination_reason,
            weekly_plan.diagnostics.failed_slot,
            weekly_plan.diagnostics.visited_states,
            weekly_plan.diagnostics.beam_iterations,
            weekly_plan.diagnostics.hard_filter_stats,
        )
        raise CatalogGenerationError(
            "Catalog planner could not produce a weekly plan",
            code=CatalogGenerationError.PLANNER_NO_PLAN,
            details={
                "diagnostics": planner_diagnostics,
                "planner_diagnostics": planner_diagnostics,
                "violations": list(weekly_plan.violations),
                "warnings": list(weekly_plan.warnings),
                "unfilled_slots": list(weekly_plan.diagnostics.unfilled_slots),
                "termination_reason": weekly_plan.diagnostics.termination_reason,
                "failed_slot": weekly_plan.diagnostics.failed_slot,
            },
        )
    planner_diagnostics = weekly_plan.diagnostics.to_dict()
    logger.warning(
        "planner_failed status=partial termination=%s failed_slot=%s "
        "visited_states=%s beam_iterations=%s hard_filters=%s",
        weekly_plan.diagnostics.termination_reason,
        weekly_plan.diagnostics.failed_slot,
        weekly_plan.diagnostics.visited_states,
        weekly_plan.diagnostics.beam_iterations,
        weekly_plan.diagnostics.hard_filter_stats,
    )
    raise CatalogGenerationError(
        "Catalog planner produced a partial plan",
        code=CatalogGenerationError.PLANNER_PARTIAL_PLAN,
        details={
            "diagnostics": planner_diagnostics,
            "planner_diagnostics": planner_diagnostics,
            "violations": list(weekly_plan.violations),
            "meal_count": len(weekly_plan.meals),
            "unfilled_slots": list(weekly_plan.diagnostics.unfilled_slots),
            "termination_reason": weekly_plan.diagnostics.termination_reason,
            "failed_slot": weekly_plan.diagnostics.failed_slot,
        },
    )


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

        # Never mutate the caller's WeeklyStrategy (cook_days / persistence).
        strategy_cook_days = list(strategy.cook_days)

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

        def _build_context(config: WeeklyPlannerConfig):
            return build_planning_context_from_strategy(
                strategy,
                excluded_ingredient_ids=excluded_ingredient_ids,
                excluded_protein_sources=excluded_proteins,
                minimum_quality_status=minimum_quality_status,
                config=config,
                strategy_id=strategy_id,
            )

        await _emit_progress(progress_callback, stage="generating")

        # Pass 1 — strict cook-day compliance (allow_cook_day_miss=False).
        strict_config = strict_planner_config()
        strict_plan = await self._planner.plan(_build_context(strict_config))

        weekly_plan = strict_plan
        relaxation_used = False
        relaxation_meta: dict[str, Any] | None = None
        explanations: list[str] = []
        strategy_warning_payload: list[dict[str, Any]] = []
        max_extra_for_finalize = 0

        if strict_plan.status == PlanStatus.SUCCESS:
            relaxation_meta = build_relaxation_metadata(
                strict_plan=strict_plan,
                relaxed_plan=strict_plan,
                strategy=strategy,
                relaxation_used=False,
            )
        elif should_attempt_cook_day_relaxation(strict_plan):
            logger.info(
                "cook_day_relaxation_attempt request_id=%s failed_slot=%s "
                "termination=%s cook_days=%s",
                request_id,
                strict_plan.diagnostics.failed_slot,
                strict_plan.diagnostics.termination_reason,
                strategy_cook_days,
            )
            await _emit_progress(progress_callback, stage="generating", attempt=2, max_attempts=2)
            relaxed_config = relaxed_planner_config()
            relaxed_plan = await self._planner.plan(_build_context(relaxed_config))
            if relaxed_plan.status != PlanStatus.SUCCESS:
                _raise_planner_failure(relaxed_plan)

            extra_days = compute_extra_cook_days_from_plan(relaxed_plan, strategy)
            if len(extra_days) > int(relaxed_config.max_extra_cook_days):
                raise CatalogGenerationError(
                    "Relaxed planner exceeded max_extra_cook_days",
                    code=CatalogGenerationError.PLANNER_PARTIAL_PLAN,
                    details={
                        "extra_cook_days": extra_days,
                        "max_extra_cook_days": relaxed_config.max_extra_cook_days,
                        "original_diagnostics": strict_plan.diagnostics.to_dict(),
                        "diagnostics": relaxed_plan.diagnostics.to_dict(),
                    },
                )

            weekly_plan = relaxed_plan
            relaxation_used = True
            max_extra_for_finalize = int(relaxed_config.max_extra_cook_days)
            relaxation_meta = build_relaxation_metadata(
                strict_plan=strict_plan,
                relaxed_plan=relaxed_plan,
                strategy=strategy,
                relaxation_used=True,
            )
            explanations.append(EXTRA_COOK_DAY_EXPLANATION_RU)
            if extra_days:
                strategy_warning_payload.append(
                    {
                        "code": EXTRA_COOK_DAY_REQUIRED,
                        "message": EXTRA_COOK_DAY_EXPLANATION_RU,
                        "path": "days_plan",
                        "extra_cook_days": extra_days,
                    }
                )
            logger.info(
                "cook_day_relaxation_applied request_id=%s extra_cook_days=%s "
                "original_failed_slot=%s",
                request_id,
                extra_days,
                strict_plan.diagnostics.failed_slot,
            )
        else:
            _raise_planner_failure(strict_plan)

        # Original strategy unchanged (including cook_days).
        assert list(strategy.cook_days) == strategy_cook_days

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
            max_extra_cook_days=max_extra_for_finalize,
            cook_day_relaxation=relaxation_meta,
            strategy_warnings=strategy_warning_payload,
            explanations=explanations,
        )

        # Ensure strategy cook_days in response metadata stay original.
        payload["strategy_cook_days"] = strategy_cook_days
        if relaxation_used and EXTRA_COOK_DAY_REQUIRED not in (
            payload.get("warnings") or []
        ):
            warnings = list(payload.get("warnings") or [])
            warnings.append(EXTRA_COOK_DAY_REQUIRED)
            payload["warnings"] = warnings

        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            "catalog_menu_generated request_id=%s user_id=%s engine=catalog_planner "
            "planner_version=%s planner_score=%s planning_duration_ms=%s "
            "catalog_recipe_count=%s meal_count=%s leftover_count=%s "
            "cooking_instance_count=%s unique_recipe_count=%s duration_ms=%s "
            "relaxation_used=%s extra_cook_days=%s",
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
            relaxation_used,
            (relaxation_meta or {}).get("extra_cook_days"),
        )
        return payload
