"""Prepare serializable generation payload (validation before Claude).

Replicates the pre-``generate_menu`` path from ``api_generate_menu`` without
importing ``main`` (avoids circular imports).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import config
import database
from api_errors import ErrorCodes
from behavior.service import BehaviorService
from decision.learned_preferences_context import (
    LearnedPreferencesContext,
    build_learned_preferences_context,
)
from generation_jobs.exceptions import GenerationPrepareError
from generation_jobs.models import PreparedGeneration
from learned_preferences.service import LearnedPreferenceService
from learning.service import LearningService
from memory.service import MemoryService
# Import strategy leaf modules before profile_validation so strategy/__init__
# finishes loading (profile_validation → strategy.memory_apply would otherwise
# re-enter an incomplete strategy package).
from strategy.behavior_context import (
    StrategyBehaviorContext,
    build_strategy_behavior_context,
)
from strategy.builder import StrategyBuilder
from strategy.conflicts import detect_strategy_conflicts
from strategy.context import ProfileContext
from strategy.exceptions import StrategyValidationError
from strategy.memory_context import (
    StrategyMemoryContext,
    build_strategy_memory_context,
)
from strategy.planner_input import build_planner_input
from strategy.preview_token import verify_preview_token
from strategy.validation import validate_strategy_for_request
from profile_validation import (
    normalize_profile_for_persistence,
    validate_profile_for_generation,
)

logger = logging.getLogger(__name__)

_strategy_builder = StrategyBuilder()
_memory_service = MemoryService()
_behavior_service = BehaviorService()
_learning_service = LearningService(
    memory_repository=_memory_service._repository,
    behavior_repository=_behavior_service._repository,
)
_learned_preference_service = LearnedPreferenceService(
    learning_repository=_learning_service._repository,
)


@dataclass(frozen=True)
class _ContextBundle:
    memory_context: StrategyMemoryContext
    memory_unavailable: bool
    behavior_context: StrategyBehaviorContext
    behavior_unavailable: bool
    learned_context: LearnedPreferencesContext
    learned_unavailable: bool


async def _load_memory_context(
    user_id: int,
) -> tuple[StrategyMemoryContext, bool]:
    try:
        confirmed_signals = await _memory_service.get_confirmed_signals(user_id)
        return build_strategy_memory_context(confirmed_signals), False
    except Exception as exc:
        logger.warning(
            "memory_context_load_failure user_id=%s error_type=%s",
            user_id,
            type(exc).__name__,
        )
        return StrategyMemoryContext.empty(), True


async def _load_behavior_context(
    user_id: int,
) -> tuple[StrategyBehaviorContext, bool]:
    try:
        confirmed = await _behavior_service.list_confirmed_insights(user_id)
        return build_strategy_behavior_context(confirmed), False
    except Exception as exc:
        logger.warning(
            "behavior_context_load_failure user_id=%s error_type=%s",
            user_id,
            type(exc).__name__,
        )
        return StrategyBehaviorContext.empty(), True


async def _load_learned_context(
    user_id: int,
) -> tuple[LearnedPreferencesContext, bool]:
    enabled = config.ADAPTIVE_PREFERENCES
    if not enabled:
        return LearnedPreferencesContext.empty(enabled=False), False
    try:
        active = await _learned_preference_service.load_active_for_decision(user_id)
        return build_learned_preferences_context(active, enabled=enabled), False
    except Exception as exc:
        logger.warning(
            "learned_preferences_context_load_failure enabled=%s error_type=%s",
            enabled,
            type(exc).__name__,
        )
        return LearnedPreferencesContext.empty(enabled=enabled), True


async def _load_contexts(user_id: int) -> _ContextBundle:
    memory_context, memory_unavailable = await _load_memory_context(user_id)
    behavior_context, behavior_unavailable = await _load_behavior_context(user_id)
    learned_context, learned_unavailable = await _load_learned_context(user_id)
    return _ContextBundle(
        memory_context=memory_context,
        memory_unavailable=memory_unavailable,
        behavior_context=behavior_context,
        behavior_unavailable=behavior_unavailable,
        learned_context=learned_context,
        learned_unavailable=learned_unavailable,
    )


def _serialize_optional_json(obj: object | None) -> str | None:
    if obj is None:
        return None
    to_json = getattr(obj, "to_json", None)
    if callable(to_json):
        return to_json()
    return None


async def prepare_generation_request(
    *,
    user_id: int,
    preview_token: str,
) -> PreparedGeneration:
    """Validate profile + token + strategy; return serializable job payload."""
    if not preview_token:
        raise GenerationPrepareError(
            code=ErrorCodes.STRATEGY_PREVIEW_REQUIRED,
            message="Приложение обновилось. Проверьте настройки ещё раз.",
            status_code=428,
        )

    contexts = await _load_contexts(user_id)

    stored = await database.get_profile(user_id)
    if stored is None:
        logger.info("generation_job_without_profile user_id=%s", user_id)
        raise GenerationPrepareError(
            code=ErrorCodes.PROFILE_REQUIRED,
            message="Проверьте настройки профиля и попробуйте ещё раз.",
            status_code=422,
        )

    persisted_profile = normalize_profile_for_persistence(stored)
    profile_revision = int(stored.get("revision", 1))
    validation = validate_profile_for_generation(persisted_profile)
    if validation.status != "valid":
        raise GenerationPrepareError(
            code=validation.code or "PERSISTED_PROFILE_INVALID",
            message="Проверьте настройки профиля и попробуйте ещё раз.",
            status_code=422,
            validation_result=validation,
        )

    verified = verify_preview_token(
        preview_token,
        user_id=user_id,
        profile=persisted_profile,
        profile_revision=profile_revision,
        memory_context=contexts.memory_context,
        behavior_context=contexts.behavior_context,
        learned_context=contexts.learned_context,
        memory_unavailable=contexts.memory_unavailable,
        behavior_unavailable=contexts.behavior_unavailable,
        learned_preferences_unavailable=contexts.learned_unavailable,
    )
    plan_start_date = date.fromisoformat(verified.payload.plan_start_date)
    logger.info(
        "generation_job_preview_verified user_id=%s plan_start_date=%s",
        user_id,
        plan_start_date.isoformat(),
    )

    profile = persisted_profile
    blocking, _ = detect_strategy_conflicts(
        ProfileContext.from_profile(profile),
        contexts.memory_context,
    )
    if blocking:
        raise StrategyValidationError(
            "Blocking strategy conflict detected after preview",
            code="STRATEGY_CONFLICT_AFTER_PREVIEW",
        )

    if contexts.learned_context.enabled:
        build_result = _strategy_builder.build_with_reasons_from_inputs(
            profile,
            contexts.memory_context,
            contexts.behavior_context,
            contexts.learned_context,
        )
    else:
        build_result = _strategy_builder.build_with_reasons_from_inputs(
            profile,
            contexts.memory_context,
            contexts.behavior_context,
        )

    strategy = build_result.strategy
    validate_strategy_for_request(
        strategy,
        days=profile.get("days"),
        budget=profile.get("budget"),
        meal_types=profile.get("meal_types"),
        meals_per_day=profile.get("meals_per_day"),
        goal=profile.get("goal"),
        proteins=profile.get("proteins"),
        allergies=profile.get("allergies"),
        dietary_constraints=profile.get("dietary_constraints"),
    )

    planner_input = build_planner_input(
        strategy=strategy,
        persons=profile.get("persons"),
        proteins=profile.get("proteins"),
        cooktime=profile.get("cooktime"),
        allergies=profile.get("allergies"),
        store=profile.get("store"),
    )

    request_payload = {
        "user_id": user_id,
        "plan_start_date": plan_start_date.isoformat(),
        "planner": {
            "budget": planner_input.budget,
            "days": planner_input.days,
            "meal_types": list(planner_input.meal_types),
            "meals_per_day": planner_input.meals_per_day,
            "persons": planner_input.persons,
            "proteins": list(planner_input.proteins),
            "goal": planner_input.goal,
            "cooktime": planner_input.cooktime,
            "allergies": planner_input.allergies,
            "store": planner_input.store,
            "strategy": strategy.model_dump(mode="json"),
        },
        "save": {
            "reason_codes": list(build_result.reason_codes),
            "applied_memory": _serialize_optional_json(build_result.applied_memory),
            "applied_cooking_preference": _serialize_optional_json(
                build_result.applied_cooking_preference
            ),
            "applied_behavior": _serialize_optional_json(
                build_result.applied_behavior
            ),
            "applied_planning_preferences": _serialize_optional_json(
                build_result.applied_planning_preferences
            ),
            "applied_learned_preferences": _serialize_optional_json(
                build_result.applied_learned_preferences
            ),
            "decision_context": _serialize_optional_json(build_result.decision_context),
            "decision_trace": _serialize_optional_json(build_result.decision_trace),
        },
    }

    return PreparedGeneration(
        request_payload=request_payload,
        days=int(planner_input.days),
        persons=int(planner_input.persons),
        plan_start_date=plan_start_date.isoformat(),
    )
