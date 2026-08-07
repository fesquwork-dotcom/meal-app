"""CatalogMealReplacementService — deterministic local meal repair (no Claude)."""

from __future__ import annotations

import logging
import time
import uuid
from pathlib import Path

import database
from memory.service import MemoryService
from menu_generation.errors import CatalogGenerationError
from menu_generation.menuplan_adapter import WeeklyRecipePlanToMenuPlanAdapter
from menu_models import DayMeal, MenuPlan
from menu_plan.exceptions import MenuPlanNotFoundError
from menu_plan.records import MenuPlanChangeType
from menu_plan.repository import MenuPlanRepository
from menu_replacement.explain import build_replacement_explanation
from menu_replacement.reasons import CatalogReplacementReason, resolve_catalog_reason
from menu_replacement.repair import (
    RepairMode,
    apply_catalog_repair,
    catalog_id_from_menu_recipe_id,
    count_leftovers_in_menu,
)
from menu_replacement.scorer import pick_best_scored, score_replacement_candidate
from menu_validation import MenuValidationRequest, validate_menu_plan
from recipes.enums import MealType
from recipes.models import Ingredient, Recipe as CatalogRecipe
from recipes.repository import RecipeRepository
from recipes.selection.selector import RecipeCandidateSelector
from recipes.selection.strategy_adapter import StrategyToCandidateContextAdapter
from strategy.compliance import validate_menu_against_strategy
from strategy.cooking_compliance import validate_cooking_contract
from strategy.exceptions import StrategyComplianceError, StrategyNotFoundError
from strategy.replacement_context import ReplacementContext, build_replacement_context
from strategy.replacement_exceptions import (
    ReplacementFailedError,
    ReplacementValidationError,
)
from strategy.replacement_models import ReplaceMealRequest, ReplaceMealResponse
from strategy.repository import StrategyRepository

logger = logging.getLogger(__name__)

CANDIDATE_LIMIT = 40


class CatalogMealReplacementService:
    def __init__(
        self,
        repository: StrategyRepository | None = None,
        memory_service: MemoryService | None = None,
        behavior_service: object | None = None,
        menu_plan_repository: MenuPlanRepository | None = None,
        *,
        db_path: Path | str | None = None,
        recipe_repository: RecipeRepository | None = None,
        selector: RecipeCandidateSelector | None = None,
        adapter: WeeklyRecipePlanToMenuPlanAdapter | None = None,
    ) -> None:
        self._repository = repository or StrategyRepository()
        self._memory_service = memory_service
        self._behavior_service = behavior_service
        self._menu_plan_repository = menu_plan_repository or MenuPlanRepository()
        self._recipe_repository = recipe_repository or RecipeRepository(db_path)
        self._selector = selector or RecipeCandidateSelector(
            repository=self._recipe_repository
        )
        self._adapter = adapter or WeeklyRecipePlanToMenuPlanAdapter(
            repository=self._recipe_repository
        )
        self._strategy_adapter = StrategyToCandidateContextAdapter()

    async def replace_meal(
        self,
        request: ReplaceMealRequest,
        *,
        user_id: int,
    ) -> ReplaceMealResponse:
        request_id = str(uuid.uuid4())
        started_at = time.monotonic()

        try:
            record = await self._repository.get_by_id(request.strategy_id, user_id)
        except StrategyNotFoundError:
            raise

        strategy = self._repository.restore_weekly_strategy(record)
        profile = await database.get_profile(user_id) or {}
        persons = int(profile.get("persons") or 2)
        validation_request = MenuValidationRequest(
            days=strategy.days,
            budget=strategy.budget,
            meal_types=list(strategy.meal_types),
            meals_per_day=strategy.meals_per_day,
            persons=persons,
            cooktime=str(profile.get("cooktime") or "medium"),
            allergies=str(profile.get("allergies") or "нет"),
            strategy_aware=True,
        )

        context = build_replacement_context(
            menu_plan=request.menu_plan,
            strategy_id=request.strategy_id,
            meal_id=request.meal_id,
            record=record,
            strategy=strategy,
            validation_request=validation_request,
        )

        reason = resolve_catalog_reason(request)
        target = context.target.meal_ref.meal
        old_catalog_id = catalog_id_from_menu_recipe_id(target.recipe_id)

        logger.info(
            "catalog_replacement_started request_id=%s user_id=%s meal_id=%s "
            "old_recipe_id=%s reason=%s",
            request_id,
            user_id,
            request.meal_id,
            old_catalog_id,
            reason.value,
        )

        mode = self._resolve_repair_mode(context, strategy.leftovers_enabled)
        force_no_cook = self._force_no_cook(context, strategy.cook_days, mode)
        prefer_batch_chain = mode == RepairMode.SOURCE_CHAIN

        current_catalog = await self._load_catalog_recipe(old_catalog_id)
        ingredients = await self._recipe_repository.list_ingredients()
        candidates, rejection_notes = await self._gather_candidates(
            context=context,
            reason=reason,
            ingredients=ingredients,
            force_no_cook=force_no_cook,
            prefer_batch_chain=prefer_batch_chain,
            target_ingredient=request.target_ingredient,
        )

        logger.info(
            "catalog_replacement_candidates request_id=%s meal_id=%s "
            "candidate_count=%s reason=%s",
            request_id,
            request.meal_id,
            len(candidates),
            reason.value,
        )

        scored = []
        for cand in candidates:
            result = score_replacement_candidate(
                cand,
                reason=reason,
                menu=context.menu_plan,
                target=target,
                current_recipe=current_catalog,
                target_ingredient=request.target_ingredient,
                day_number=context.target.day_number,
                cook_days=set(strategy.cook_days),
                force_no_cook=force_no_cook,
            )
            if result is not None:
                scored.append(result)

        best = pick_best_scored(scored)
        if best is None:
            duration_ms = int((time.monotonic() - started_at) * 1000)
            logger.info(
                "catalog_replacement_failed request_id=%s meal_id=%s reason=%s "
                "candidate_count=%s duration_ms=%s",
                request_id,
                request.meal_id,
                reason.value,
                len(candidates),
                duration_ms,
            )
            raise CatalogGenerationError(
                "No suitable catalog replacement found",
                code=CatalogGenerationError.CATALOG_REPLACEMENT_NOT_FOUND,
                details={
                    "meal_id": request.meal_id,
                    "reason": reason.value,
                    "candidate_count": len(candidates),
                    "top_rejection_reasons": rejection_notes[:8],
                    "constraints": {
                        "force_no_cook": force_no_cook,
                        "repair_mode": mode.value,
                        "old_recipe_id": old_catalog_id,
                    },
                },
            )

        selected = best.candidate.recipe
        logger.info(
            "catalog_replacement_selected request_id=%s meal_id=%s "
            "old_recipe_id=%s new_recipe_id=%s reason=%s",
            request_id,
            request.meal_id,
            old_catalog_id,
            selected.id,
            reason.value,
        )

        repaired = apply_catalog_repair(
            context,
            catalog=selected,
            persons=persons,
            mode=mode,
            adapter=self._adapter,
        )
        self._validate_merged_plan(
            repaired.menu_plan, strategy, validation_request
        )

        explanation = build_replacement_explanation(
            old_recipe=current_catalog,
            new_recipe=selected,
            reason=reason,
            machine_reasons=best.machine_reasons,
        )

        new_revision = await self._persist_revision(
            request, user_id, repaired.menu_plan, repaired.changed_meal_ids
        )
        memory_metadata = await self._record_memory(request, user_id)
        if memory_metadata is not None:
            await self._evaluate_behavior(user_id)

        duration_ms = int((time.monotonic() - started_at) * 1000)
        logger.info(
            "catalog_replacement_completed request_id=%s meal_id=%s "
            "old_recipe_id=%s new_recipe_id=%s reason=%s candidate_count=%s "
            "changed_slots_count=%s duration_ms=%s",
            request_id,
            request.meal_id,
            old_catalog_id,
            selected.id,
            reason.value,
            len(candidates),
            len(repaired.changed_meal_ids),
            duration_ms,
        )

        return ReplaceMealResponse(
            menu_plan=repaired.menu_plan,
            replaced_meal_id=request.meal_id,
            changed_meal_ids=repaired.changed_meal_ids,
            memory=memory_metadata,
            menu_plan_id=request.menu_plan_id if new_revision else None,
            revision=new_revision,
            explanation=explanation,
            replacement_reasons=list(best.machine_reasons),
            replacement_engine="catalog_selector",
        )

    def _resolve_repair_mode(
        self, context: ReplacementContext, leftovers_enabled: bool
    ) -> RepairMode:
        target = context.target.meal_ref.meal
        downstream = context.target.downstream_refs

        if target.uses_leftovers:
            # Prefer independent slot when other leftovers keep strategy satisfied
            # and the target day allows cooking (or no-cook recipes). Otherwise
            # repair the source+leftover chain so non-cook days stay valid.
            remaining_after = count_leftovers_in_menu(context.menu_plan) - 1
            if leftovers_enabled and remaining_after < 1:
                return RepairMode.SOURCE_CHAIN
            if context.target.day_number not in set(
                context.strategy.cook_days
            ):
                return RepairMode.SOURCE_CHAIN
            return RepairMode.LEFTOVER_TO_INDEPENDENT

        if downstream:
            return RepairMode.SOURCE_CHAIN
        return RepairMode.SINGLE_SLOT

    def _force_no_cook(
        self,
        context: ReplacementContext,
        cook_days: list[int],
        mode: RepairMode,
    ) -> bool:
        if mode == RepairMode.SOURCE_CHAIN:
            # Source cook day must remain a cook day for cooking recipes.
            target = context.target.meal_ref.meal
            if target.uses_leftovers and target.source_meal_id:
                # Source day drives cooking; leftover day may be non-cook.
                return False
            return context.target.day_number not in set(cook_days)
        return context.target.day_number not in set(cook_days)

    async def _load_catalog_recipe(
        self, catalog_id: str | None
    ) -> CatalogRecipe | None:
        if not catalog_id:
            return None
        return await self._recipe_repository.get_recipe_with_dependencies(catalog_id)

    async def _gather_candidates(
        self,
        *,
        context: ReplacementContext,
        reason: CatalogReplacementReason,
        ingredients: list[Ingredient],
        force_no_cook: bool,
        prefer_batch_chain: bool,
        target_ingredient: str | None,
    ) -> tuple[list, list[str]]:
        target = context.target.meal_ref.meal
        meal_type = MealType(target.type)
        sel_context, _adapter_result = self._strategy_adapter.adapt(
            context.strategy,
            meal_type=meal_type,
            ingredients=ingredients,
            limit=CANDIDATE_LIMIT,
        )

        avoid = set(sel_context.avoid_recipe_ids)
        current_id = catalog_id_from_menu_recipe_id(target.recipe_id)
        if current_id:
            avoid.add(current_id)
        avoid |= self._week_avoid_ids(context.menu_plan, target, context.strategy)

        updates: dict = {"avoid_recipe_ids": avoid, "limit": CANDIDATE_LIMIT}
        if reason == CatalogReplacementReason.TOO_LONG and context.target.recipe:
            # Soft preference only via local scorer; optional tighter selector cap
            # would change global behavior — keep selector max_time from strategy.
            pass
        if prefer_batch_chain:
            updates["prefer_batch_friendly"] = True
            updates["allow_leftovers"] = True

        sel_context = sel_context.model_copy(update=updates)
        selection = await self._selector.select(sel_context)

        rejection_notes: list[str] = []
        if selection.filter_stats.removed:
            for code, count in sorted(selection.filter_stats.removed.items()):
                rejection_notes.append(f"{code}:{count}")
        if force_no_cook:
            rejection_notes.append("force_no_cook")
        if target_ingredient:
            rejection_notes.append(f"exclude_ingredient:{target_ingredient}")

        return list(selection.candidates), rejection_notes

    def _week_avoid_ids(
        self, menu: MenuPlan, target: DayMeal, strategy
    ) -> set[str]:
        repeat_allowed = {
            "breakfast": bool(strategy.repeat_breakfasts),
            "lunch": bool(strategy.repeat_lunches),
            "dinner": bool(strategy.repeat_dinners),
        }.get(target.type, False)
        if repeat_allowed:
            return set()
        ids: set[str] = set()
        for day in menu.days_plan:
            for meal in day.meals:
                if meal.meal_id == target.meal_id:
                    continue
                if meal.type != target.type:
                    continue
                rid = catalog_id_from_menu_recipe_id(meal.recipe_id)
                if rid:
                    ids.add(rid)
        return ids

    def _validate_merged_plan(
        self,
        merged: MenuPlan,
        strategy,
        validation_request: MenuValidationRequest,
    ) -> None:
        result = validate_menu_plan(merged, validation_request)
        if not result.is_valid:
            raise ReplacementValidationError(
                "Merged menu plan failed validation",
                issue_codes=[issue.code for issue in result.errors],
                issue_messages=[
                    f"{issue.message} (path: {issue.path})" if issue.path else issue.message
                    for issue in result.errors
                ],
            )
        try:
            validate_menu_against_strategy(merged, strategy)
            validate_cooking_contract(merged, strategy)
        except StrategyComplianceError as exc:
            raise ReplacementFailedError(issue_codes=exc.issue_codes) from exc

    async def _persist_revision(
        self,
        request: ReplaceMealRequest,
        user_id: int,
        merged: MenuPlan,
        changed_ids: list[str],
    ) -> int | None:
        if request.menu_plan_id is None or request.expected_revision is None:
            return None
        record = await self._menu_plan_repository.get_by_id(
            request.menu_plan_id, user_id
        )
        if record.strategy_id != request.strategy_id:
            raise MenuPlanNotFoundError(
                f"Menu plan not found: {request.menu_plan_id}"
            )
        return await self._menu_plan_repository.append_revision(
            menu_plan_id=request.menu_plan_id,
            user_id=user_id,
            expected_revision=request.expected_revision,
            plan_json=merged.model_dump_json(),
            change_type=MenuPlanChangeType.MEAL_REPLACEMENT,
            changed_meal_ids=changed_ids,
        )

    async def _record_memory(
        self, request: ReplaceMealRequest, user_id: int
    ) -> dict | None:
        if self._memory_service is None:
            return None
        try:
            recipe_id = None
            for day in request.menu_plan.days_plan:
                for meal in day.meals:
                    if meal.meal_id == request.meal_id:
                        recipe_id = meal.recipe_id
                        break
            result = await self._memory_service.record_meal_replaced(
                user_id=user_id,
                strategy_id=request.strategy_id,
                meal_id=request.meal_id,
                recipe_id=recipe_id,
                reason_code=request.reason_code,
                target_ingredient=request.target_ingredient,
                event_key=request.replacement_request_id,
            )
            return {
                "event_recorded": result.event_recorded,
                "signal_updated": result.signal_updated,
            }
        except Exception:
            logger.warning(
                "memory_side_effect_failed strategy_id=%s reason_code=%s",
                request.strategy_id,
                request.reason_code,
                exc_info=True,
            )
            return None

    async def _evaluate_behavior(self, user_id: int) -> None:
        if self._behavior_service is None:
            return
        try:
            await self._behavior_service.evaluate_user(user_id)
        except Exception:
            logger.warning(
                "behavior_evaluation_hook_failed user_id=%s",
                user_id,
                exc_info=True,
            )
