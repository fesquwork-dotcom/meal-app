"""Orchestrates single-meal replacement with Claude and validation."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid

import httpx
from pydantic import ValidationError

import config
import database
from anthropic_http import (
    compute_retry_delay_seconds,
    create_anthropic_client,
    is_retryable_anthropic_status,
    parse_anthropic_error,
)
from memory.service import MemoryService
from claude_exceptions import (
    ClaudeJsonError,
    ClaudeTimeoutError,
    ClaudeUnavailableError,
    ClaudeValidationError,
    MenuConstraintError,
)
from claude_json import extract_json_object
from menu_generation.engine import GenerationEngine, resolve_generation_engine
from menu_models import MenuPlan
from menu_plan.exceptions import MenuPlanNotFoundError
from menu_plan.records import MenuPlanChangeType
from menu_plan.repository import MenuPlanRepository
from menu_replacement.service import CatalogMealReplacementService
from menu_validation import MenuValidationRequest, validate_menu_plan
from strategy.compliance import validate_menu_against_strategy
from strategy.cooking_compliance import validate_cooking_contract
from strategy.exceptions import StrategyComplianceError, StrategyNotFoundError
from strategy.records import StrategyStatus
from strategy.repository import StrategyRepository
from strategy.replacement_constants import MAX_REPLACEMENT_LLM_ATTEMPTS
from strategy.replacement_context import build_replacement_context
from strategy.replacement_exceptions import (
    ReplacementFailedError,
    ReplacementPriceResolutionError,
    ReplacementValidationError,
)
from strategy.replacement_merge import merge_replacement
from strategy.replacement_models import (
    ReplaceMealRequest,
    ReplaceMealResponse,
    ReplacementLLMResponse,
)
from strategy.replacement_prompt import (
    build_replacement_correction_prompt,
    build_replacement_system_prompt,
    build_replacement_user_prompt,
)

logger = logging.getLogger(__name__)

_MAX_LOG_UNRESOLVED_NAMES = 12
_MAX_LOG_NAME_CHARS = 40


def _safe_unresolved_for_log(unresolved: tuple[str, ...] | list[str]) -> list[str]:
    if config.ENVIRONMENT == "production":
        return []
    safe: list[str] = []
    for name in unresolved[:_MAX_LOG_UNRESOLVED_NAMES]:
        cleaned = " ".join(str(name).split())
        if not cleaned:
            continue
        if len(cleaned) > _MAX_LOG_NAME_CHARS:
            cleaned = cleaned[: _MAX_LOG_NAME_CHARS - 1] + "…"
        safe.append(cleaned)
    return safe


class MealReplacementService:
    def __init__(
        self,
        repository: StrategyRepository | None = None,
        memory_service: MemoryService | None = None,
        behavior_service: object | None = None,
        menu_plan_repository: MenuPlanRepository | None = None,
        catalog_service: CatalogMealReplacementService | None = None,
    ) -> None:
        self._repository = repository or StrategyRepository()
        self._memory_service = memory_service
        self._behavior_service = behavior_service
        self._menu_plan_repository = menu_plan_repository or MenuPlanRepository()
        self._catalog_service = catalog_service or CatalogMealReplacementService(
            repository=self._repository,
            memory_service=memory_service,
            behavior_service=behavior_service,
            menu_plan_repository=self._menu_plan_repository,
        )

    @staticmethod
    def _is_catalog_planner_menu(menu_plan: MenuPlan) -> bool:
        """Block Claude replace for catalog-generated menus.

        Prefer the persisted ``generation_engine`` field on MenuPlan. Config
        ``catalog_planner`` alone does not block legacy Claude menus (field
        absent / None) so pre-10.11 plans remain replaceable.
        """
        plan_engine = getattr(menu_plan, "generation_engine", None)
        if isinstance(plan_engine, str) and plan_engine.strip().lower() == (
            GenerationEngine.CATALOG_PLANNER.value
        ):
            return True
        engine = resolve_generation_engine()
        if engine == GenerationEngine.CATALOG_PLANNER and isinstance(plan_engine, str):
            return plan_engine.strip().lower() == GenerationEngine.CATALOG_PLANNER.value
        return False

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
        except StrategyNotFoundError as exc:
            raise StrategyNotFoundError(str(exc)) from exc

        strategy = self._repository.restore_weekly_strategy(record)

        if self._is_catalog_planner_menu(request.menu_plan):
            # Sprint 10.12 — route catalog menus to deterministic replacement.
            # Never fall back to Claude for catalog_planner menus.
            return await self._catalog_service.replace_meal(
                request, user_id=user_id
            )

        profile = await database.get_profile(user_id) or {}
        validation_request = MenuValidationRequest(
            days=strategy.days,
            budget=strategy.budget,
            meal_types=list(strategy.meal_types),
            meals_per_day=strategy.meals_per_day,
            persons=int(profile.get("persons") or 2),
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

        logger.info(
            "replacement_started request_id=%s user_id=%s strategy_id=%s target_meal_id=%s "
            "downstream_count=%s strategy_status=%s",
            request_id,
            user_id,
            request.strategy_id,
            request.meal_id,
            len(context.target.downstream_refs),
            record.status,
        )

        system = build_replacement_system_prompt(strategy)
        base_prompt = build_replacement_user_prompt(context, request.reason)
        correction_suffix = ""

        last_error: Exception | None = None

        for attempt in range(1, MAX_REPLACEMENT_LLM_ATTEMPTS + 1):
            prompt = base_prompt + correction_suffix
            try:
                raw = await self._call_claude(system, prompt, request_id=request_id)
                payload = extract_json_object(raw)
                llm_response = ReplacementLLMResponse.model_validate(payload)
                merged = merge_replacement(context, llm_response)
                self._validate_merged_plan(merged, strategy, validation_request)

                duration_ms = int((time.monotonic() - started_at) * 1000)
                changed_ids = [request.meal_id]
                for affected in llm_response.affected_meals:
                    if affected.meal.meal_id and affected.meal.meal_id not in changed_ids:
                        changed_ids.append(affected.meal.meal_id)

                logger.info(
                    "replacement_success request_id=%s strategy_id=%s target_meal_id=%s "
                    "changed_meal_ids=%s affected_count=%s attempts=%s duration_ms=%s",
                    request_id,
                    request.strategy_id,
                    request.meal_id,
                    changed_ids,
                    len(llm_response.affected_meals),
                    attempt,
                    duration_ms,
                )

                # Sprint 7.2: persist the validated state as an append-only
                # revision BEFORE side effects, so a CAS conflict aborts the
                # replacement cleanly without recording phantom memory events.
                new_revision = await self._persist_revision(
                    request, user_id, merged, changed_ids
                )

                memory_metadata = await self._record_memory(request, user_id)
                if memory_metadata is not None:
                    await self._evaluate_behavior(user_id)

                return ReplaceMealResponse(
                    menu_plan=merged,
                    replaced_meal_id=request.meal_id,
                    changed_meal_ids=changed_ids,
                    memory=memory_metadata,
                    menu_plan_id=request.menu_plan_id if new_revision else None,
                    revision=new_revision,
                )
            except (ClaudeJsonError, ClaudeValidationError, ValidationError) as exc:
                last_error = exc
                if attempt >= MAX_REPLACEMENT_LLM_ATTEMPTS:
                    raise ClaudeValidationError("Replacement schema validation failed") from exc
                correction_suffix = (
                    "\n\nИСПРАВЛЕНИЕ: ответ не соответствует JSON-схеме замены. "
                    "Верни валидный JSON-контракт замены."
                )
            except (StrategyComplianceError, MenuConstraintError, ReplacementValidationError) as exc:
                last_error = exc
                if attempt >= MAX_REPLACEMENT_LLM_ATTEMPTS:
                    if isinstance(exc, StrategyComplianceError):
                        raise ReplacementFailedError(issue_codes=exc.issue_codes) from exc
                    if isinstance(exc, ReplacementValidationError):
                        raise ReplacementFailedError(issue_codes=exc.issue_codes) from exc
                    if isinstance(exc, MenuConstraintError):
                        raise ReplacementFailedError(issue_codes=exc.issue_codes) from exc
                    raise

                issue_codes = getattr(exc, "issue_codes", [])
                messages = getattr(exc, "messages", [str(exc)])
                if isinstance(exc, MenuConstraintError):
                    messages = [f"Menu constraint: {code}" for code in issue_codes]
                if isinstance(exc, ReplacementValidationError):
                    detailed = getattr(exc, "issue_messages", [])
                    messages = (
                        detailed
                        if len(detailed) == len(issue_codes)
                        else [f"Validation: {code}" for code in issue_codes]
                    )

                logger.warning(
                    "replacement_retry request_id=%s attempt=%s issue_codes=%s",
                    request_id,
                    attempt,
                    issue_codes,
                )
                correction_suffix = (
                    "\n\n"
                    + build_replacement_correction_prompt(
                        issue_codes,
                        messages,
                        context,
                        request.meal_id,
                    )
                )
            except ReplacementPriceResolutionError as exc:
                last_error = exc
                logger.warning(
                    "replacement_price_resolution_failed request_id=%s "
                    "unresolved_count=%s canonicalization_stage=%s retry_attempt=%s "
                    "unresolved_names=%s",
                    request_id,
                    len(exc.unresolved_items),
                    "basket_rebuild",
                    attempt,
                    _safe_unresolved_for_log(exc.unresolved_items),
                )
                if attempt >= MAX_REPLACEMENT_LLM_ATTEMPTS:
                    raise

                issue_codes = list(exc.issue_codes)
                messages = [
                    "Некоторые ингредиенты невозможно сопоставить с доступным каталогом цен."
                ]
                correction_suffix = (
                    "\n\n"
                    + build_replacement_correction_prompt(
                        issue_codes,
                        messages,
                        context,
                        request.meal_id,
                        unresolved_items=exc.unresolved_items,
                    )
                )
            except ClaudeTimeoutError:
                raise
            except ClaudeUnavailableError:
                raise

        if last_error:
            raise last_error
        raise ClaudeUnavailableError("Replacement failed without result")

    async def _persist_revision(
        self,
        request: ReplaceMealRequest,
        user_id: int,
        merged,
        changed_ids: list[str],
    ) -> int | None:
        """Append the merged plan as the next durable revision (CAS-guarded).

        Legacy requests without menu_plan_id skip persistence entirely and
        keep the pre-7.2 behavior.
        """
        if request.menu_plan_id is None or request.expected_revision is None:
            return None
        record = await self._menu_plan_repository.get_by_id(
            request.menu_plan_id, user_id
        )
        if record.strategy_id != request.strategy_id:
            # The durable plan belongs to a different strategy; treat as
            # missing rather than leak cross-plan state.
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
        """Records the replacement as a memory side effect.

        Non-critical: any failure is logged and swallowed so a successful
        replacement is never turned into an error, and Claude is not re-called.
        """
        if self._memory_service is None:
            return None

        try:
            recipe_id = self._target_recipe_id(request)
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

    @staticmethod
    def _target_recipe_id(request: ReplaceMealRequest) -> str | None:
        for day in request.menu_plan.days_plan:
            for meal in day.meals:
                if meal.meal_id == request.meal_id:
                    return meal.recipe_id
        return None

    def _validate_merged_plan(
        self,
        merged,
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
        validate_menu_against_strategy(merged, strategy)
        validate_cooking_contract(merged, strategy)

    async def _call_claude(
        self,
        system: str,
        prompt: str,
        *,
        request_id: str,
    ) -> str:
        for attempt in range(1, MAX_REPLACEMENT_LLM_ATTEMPTS + 1):
            try:
                async with create_anthropic_client() as client:
                    response = await client.post(
                        "https://api.anthropic.com/v1/messages",
                        headers={
                            "x-api-key": config.ANTHROPIC_API_KEY,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": config.CLAUDE_MODEL,
                            "max_tokens": config.CLAUDE_MAX_TOKENS,
                            "system": system,
                            "messages": [{"role": "user", "content": prompt}],
                        },
                    )
            except httpx.TimeoutException as exc:
                raise ClaudeTimeoutError("Claude request timed out") from exc
            except httpx.HTTPError as exc:
                raise ClaudeUnavailableError("Claude API request failed") from exc

            if response.status_code == 200:
                data = response.json()
                return "".join(
                    block["text"]
                    for block in data.get("content", [])
                    if block.get("type") == "text"
                )

            provider_error = parse_anthropic_error(response)

            if is_retryable_anthropic_status(response.status_code):
                if attempt >= MAX_REPLACEMENT_LLM_ATTEMPTS:
                    logger.error(
                        "replacement_generation_failed request_id=%s status=%s "
                        "configured_model=%s "
                        "provider_error_type=%s provider_message=%s "
                        "provider_request_id=%s",
                        request_id,
                        response.status_code,
                        config.CLAUDE_MODEL,
                        provider_error.error_type,
                        provider_error.error_message,
                        provider_error.anthropic_request_id,
                    )
                    raise ClaudeUnavailableError("Claude API returned non-200 status")

                delay_seconds = compute_retry_delay_seconds(attempt, response)
                logger.warning(
                    "anthropic_retry request_id=%s attempt=%s max_attempts=%s "
                    "status=%s provider_error_type=%s delay_seconds=%s",
                    request_id,
                    attempt,
                    MAX_REPLACEMENT_LLM_ATTEMPTS,
                    response.status_code,
                    provider_error.error_type,
                    delay_seconds,
                )
                await asyncio.sleep(delay_seconds)
                continue

            logger.error(
                "replacement_generation_failed request_id=%s status=%s "
                "configured_model=%s "
                "provider_error_type=%s provider_message=%s provider_request_id=%s",
                request_id,
                response.status_code,
                config.CLAUDE_MODEL,
                provider_error.error_type,
                provider_error.error_message,
                provider_error.anthropic_request_id,
            )
            raise ClaudeUnavailableError("Claude API returned non-200 status")

        raise ClaudeUnavailableError("Claude API returned non-200 status")
