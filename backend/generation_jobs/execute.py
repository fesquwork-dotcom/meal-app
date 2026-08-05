"""Execute a queued generation job: Claude + strategy/menu save."""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import date

from claude_exceptions import ClaudeValidationError
from claude_service import MAX_LLM_ATTEMPTS
from decision.context import DecisionContext
from decision.trace_models import DecisionTrace
from generation_jobs.errors import (
    ERROR_CODE_SAVE_FAILED,
    SAFE_MESSAGE_SAVE_FAILED,
    map_generation_exception,
)
from menu_generation.orchestrator import generate_menu
from generation_jobs.models import JobStage
from generation_jobs.repository import GenerationJobRepository
from menu_models import MenuPlan
from strategy.applied_behavior import AppliedBehaviorSnapshot
from strategy.applied_cooking import AppliedCookingPreference
from strategy.applied_learned_preferences import AppliedLearnedPreferencesSnapshot
from strategy.applied_planning import AppliedPlanningPreferences
from strategy.memory_context import AppliedMemorySnapshot
from strategy.models import WeeklyStrategy
from strategy.service import StrategyService

logger = logging.getLogger(__name__)

_repository = GenerationJobRepository()
_strategy_service = StrategyService()


def _deserialize_save_bundle(save: dict) -> dict:
    applied_memory_raw = save.get("applied_memory")
    applied_cooking_raw = save.get("applied_cooking_preference")
    applied_behavior_raw = save.get("applied_behavior")
    applied_planning_raw = save.get("applied_planning_preferences")
    applied_learned_raw = save.get("applied_learned_preferences")
    decision_context_raw = save.get("decision_context")
    decision_trace_raw = save.get("decision_trace")

    return {
        "reason_codes": list(save.get("reason_codes") or []),
        "applied_memory": AppliedMemorySnapshot.from_json(applied_memory_raw)
        if isinstance(applied_memory_raw, str)
        else None,
        "applied_cooking_preference": AppliedCookingPreference.from_json(
            applied_cooking_raw
        )
        if isinstance(applied_cooking_raw, str)
        else None,
        "applied_behavior": AppliedBehaviorSnapshot.from_json(applied_behavior_raw)
        if isinstance(applied_behavior_raw, str)
        else None,
        "applied_planning_preferences": AppliedPlanningPreferences.from_json(
            applied_planning_raw
        )
        if isinstance(applied_planning_raw, str)
        else None,
        "applied_learned_preferences": AppliedLearnedPreferencesSnapshot.from_json(
            applied_learned_raw
        )
        if isinstance(applied_learned_raw, str)
        else None,
        "decision_context": DecisionContext.from_json(decision_context_raw)
        if isinstance(decision_context_raw, str)
        else None,
        "decision_trace": DecisionTrace.from_json(decision_trace_raw)
        if isinstance(decision_trace_raw, str)
        else None,
    }


async def run_generation_job(job_id: str) -> None:
    """Load job, run generate_menu + save_active_strategy, update status."""
    started = time.monotonic()
    job = await _repository.get(job_id)
    if job is None:
        logger.warning("generation_job_missing job_id=%s", job_id)
        return
    if job.status != "queued":
        logger.info(
            "generation_job_skip status=%s job_id=%s",
            job.status,
            job_id,
        )
        return

    raw_json = job.request_json or ""
    if not raw_json.strip():
        await _repository.mark_failed(
            job_id,
            error_code=ERROR_CODE_SAVE_FAILED,
            safe_message=SAFE_MESSAGE_SAVE_FAILED,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return

    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError:
        logger.exception("generation_job_payload_invalid job_id=%s", job_id)
        await _repository.mark_failed(
            job_id,
            error_code=ERROR_CODE_SAVE_FAILED,
            safe_message=SAFE_MESSAGE_SAVE_FAILED,
            duration_ms=int((time.monotonic() - started) * 1000),
        )
        return

    running = await _repository.mark_running(
        job_id,
        clear_request_json=True,
        max_attempts=MAX_LLM_ATTEMPTS,
    )
    # mark_running returns None when another worker already claimed this job.
    if running is None:
        logger.info("generation_job_claim_failed job_id=%s", job_id)
        return

    user_id = int(payload["user_id"])
    plan_start_date = date.fromisoformat(str(payload["plan_start_date"]))
    planner = payload["planner"]
    save_bundle = _deserialize_save_bundle(payload.get("save") or {})
    strategy = WeeklyStrategy.model_validate(planner["strategy"])

    async def progress_callback(
        *,
        stage: str,
        attempt: int | None = None,
        max_attempts: int | None = None,
        **_kwargs: object,
    ) -> None:
        await _repository.update_stage(
            job_id,
            stage=stage,
            attempt=attempt,
            max_attempts=max_attempts or MAX_LLM_ATTEMPTS,
        )

    try:
        result = await generate_menu(
            budget=float(planner["budget"]),
            days=int(planner["days"]),
            meal_types=list(planner["meal_types"]),
            meals_per_day=int(planner["meals_per_day"]),
            persons=int(planner["persons"]),
            proteins=list(planner["proteins"]),
            goal=str(planner["goal"]),
            cooktime=str(planner["cooktime"]),
            allergies=str(planner["allergies"]),
            store=str(planner.get("store") or "any"),
            strategy=strategy,
            user_id=user_id,
            plan_start_date=plan_start_date,
            progress_callback=progress_callback,
        )

        await _repository.update_stage(job_id, stage=JobStage.SAVING.value)

        resolved_start = plan_start_date
        if isinstance(result.get("plan_start_date"), str):
            resolved_start = date.fromisoformat(result["plan_start_date"])

        try:
            durable_plan = MenuPlan.model_validate(result)
        except ValueError as exc:
            details: list[str] = []
            if hasattr(exc, "errors"):
                try:
                    details = [
                        f"{'.'.join(str(part) for part in err.get('loc', ()))}: "
                        f"{err.get('msg', 'invalid')}"
                        for err in exc.errors()[:12]
                    ]
                except Exception:
                    details = [str(exc)]
            else:
                details = [str(exc)]
            logger.exception(
                "generation_job_menu_plan_validation_failed job_id=%s details=%s",
                job_id,
                details,
            )
            raise ClaudeValidationError(
                "Menu plan snapshot validation failed",
                details=details,
            ) from exc

        # Guard: only the claimed runner may persist; skip if job left running.
        current = await _repository.get(job_id)
        if current is None or current.status != "running":
            logger.warning(
                "generation_job_persist_skipped status=%s job_id=%s",
                None if current is None else current.status,
                job_id,
            )
            return

        menu_plan_id = str(uuid.uuid4())
        try:
            strategy_id = await _strategy_service.save_active_strategy(
                user_id=user_id,
                strategy=strategy,
                plan_start_date=resolved_start,
                reason_codes=save_bundle["reason_codes"],
                applied_memory=save_bundle["applied_memory"],
                applied_cooking_preference=save_bundle["applied_cooking_preference"],
                applied_behavior=save_bundle["applied_behavior"],
                applied_planning_preferences=save_bundle[
                    "applied_planning_preferences"
                ],
                applied_learned_preferences=save_bundle[
                    "applied_learned_preferences"
                ],
                decision_context=save_bundle["decision_context"],
                decision_trace=save_bundle["decision_trace"],
                menu_plan_id=menu_plan_id,
                menu_plan_json=durable_plan.model_dump_json(),
            )
        except Exception:
            logger.exception(
                "generation_job_menu_save_failed job_id=%s menu_plan_id=%s",
                job_id,
                menu_plan_id,
            )
            await _repository.mark_failed(
                job_id,
                error_code=ERROR_CODE_SAVE_FAILED,
                safe_message=SAFE_MESSAGE_SAVE_FAILED,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
            return

        duration_ms = int((time.monotonic() - started) * 1000)
        await _repository.mark_succeeded(
            job_id,
            strategy_id=strategy_id,
            menu_plan_id=menu_plan_id,
            duration_ms=duration_ms,
        )
        logger.info(
            "generation_job_succeeded job_id=%s user_id=%s strategy_id=%s "
            "menu_plan_id=%s duration_ms=%s",
            job_id,
            user_id,
            strategy_id,
            menu_plan_id,
            duration_ms,
        )
    except Exception as exc:
        error_code, safe_message = map_generation_exception(exc)
        error_details = None
        from menu_generation.errors import CatalogGenerationError

        if isinstance(exc, CatalogGenerationError) and exc.details:
            error_details = dict(exc.details)
        logger.exception(
            "generation_job_failed job_id=%s error_code=%s error_type=%s",
            job_id,
            error_code,
            type(exc).__name__,
        )
        await _repository.mark_failed(
            job_id,
            error_code=error_code,
            safe_message=safe_message,
            duration_ms=int((time.monotonic() - started) * 1000),
            error_details=error_details,
        )
