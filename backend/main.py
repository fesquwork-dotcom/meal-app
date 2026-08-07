import logging
import uuid
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

import config
import database
from api_errors import ApiErrorResponse, ApiFieldError, ErrorCodes, api_error_response, new_request_id
from api_models import (
    GenerateMenuRequest,
    PositiveEventRequest,
    PositiveEventResponse,
    PositiveEventUndoResponse,
    ResolveConflictRequest,
    StrategyCompareRequest,
    StrategyPreviewRequest,
)
from auth import get_current_telegram_user
from dietary_constraints import (
    DietaryConstraintError,
    constraint_counts_by_kind,
    constraints_from_profile,
    normalize_constraints,
    parse_legacy_allergies,
    serialize_legacy_allergies,
)
from claude_exceptions import (
    ClaudeJsonError,
    ClaudeOutputTruncatedError,
    ClaudeTimeoutError,
    ClaudeUnavailableError,
    ClaudeValidationError,
    MenuConstraintError,
)
from menu_generation.errors import CatalogGenerationError
from menu_generation.orchestrator import generate_menu
from meal_types import DEFAULT_MEAL_TYPES, resolve_meal_types
from menu_models import MenuPlan
from behavior.api_models import (
    BehaviorInsightActionResponse,
    BehaviorInsightsListResponse,
    BehaviorRevokeResponse,
    BehaviorSnoozeRequest,
)
from behavior.exceptions import (
    BehaviorEvaluationError,
    BehaviorInsightInvalidTransitionError,
    BehaviorInsightNotConfirmableError,
    BehaviorInsightNotDismissibleError,
    BehaviorInsightNotFoundError,
    BehaviorInsightNotRevokableError,
    BehaviorInsightNotSnoozableError,
    BehaviorRecommendationFailedError,
    BehaviorRecommendationNotAvailableError,
    BehaviorRecommendationProfileStaleError,
    BehaviorRevokeFailedError,
    BehaviorServiceUnavailableError,
    BehaviorSnoozeFailedError,
)
from behavior.recommendation_models import (
    ApplyBehaviorRecommendationRequest,
    ApplyBehaviorRecommendationResponse,
)
from behavior.service import BehaviorService
from memory.exceptions import (
    MemoryPromotionFailedError,
    MemoryPromotionProfileStaleError,
    MemorySignalAlreadyPromotedError,
    MemorySignalNotConfirmedError,
    MemorySignalNotFoundError,
    MemorySignalNotPromotableError,
)
from memory.promotion_models import PromoteMemorySignalRequest, PromoteMemorySignalResponse
from memory.promotion_service import MemoryPromotionService
from memory.positive_events import (
    PositiveEventNotAllowedError,
    PositiveEventService,
    PositiveEventValidationError,
)
from memory.service import MemoryService
from learning.models import (
    LearningAcceptResponse,
    LearningDismissResponse,
    LearningRecommendationSummary,
)
from learning.repository import (
    LearningPersistenceError,
    LearningRecommendationNotFoundError,
    LearningRecommendationTransitionError,
)
from learning.service import LearningService
from learned_preferences.api_models import LearnedPreferencesResponse
from learned_preferences.exceptions import (
    LearnedPreferenceNotAvailableError,
    LearnedPreferenceNotFoundError,
    LearnedPreferencePersistenceError,
)
from learned_preferences.service import LearnedPreferenceService
from decision.learned_preferences_context import (
    LearnedPreferencesContext,
    build_learned_preferences_context,
)
from insights.api_models import InsightSummaryResponse
from insights.service import InsightService
from menu_plan.exceptions import (
    MenuPlanConcurrencyError,
    MenuPlanNotFoundError,
    MenuPlanPersistenceError,
)
from menu_plan.service import (
    DEFAULT_HISTORY_PAGE_SIZE,
    MenuPlanService,
    decode_history_cursor,
)
from plan_delta.service import PlanDeltaService
from trends.api_models import TrendSummaryResponse
from trends.summary import TrendService
from strategy.context import ProfileContext
from strategy.conflict_resolution_service import ConflictResolutionService
from strategy.conflicts import detect_strategy_conflicts
from profile_models import ProfilePayload, ProfileResponse, UpdateProfileRequest
from profile_validation import (
    ProfileValidationResult,
    normalize_profile_for_persistence,
    validate_profile_for_generation,
    validate_profile_payload,
)
from strategy.compare_models import StrategyCompareResponse
from strategy.compare_service import StrategyCompareService
from strategy.exceptions import ConflictNotFoundError, StrategyPreviewStaleError
from strategy.preview_models import ResolveConflictResponse
from strategy.preview_service import StrategyPreviewService
from strategy.preview_token import PreviewTokenError, verify_preview_token
from strategy.behavior_context import StrategyBehaviorContext, build_strategy_behavior_context
from strategy.memory_context import StrategyMemoryContext, build_strategy_memory_context
from strategy import (
    StrategyBuilder,
    StrategyValidationError,
    build_planner_input,
    validate_strategy_for_request,
)
from strategy.exceptions import (
    StrategyNotFoundError,
    StrategyPersistenceError,
    UnsupportedStrategyVersionError,
)
from strategy.replacement_exceptions import (
    MealNotFoundError,
    MenuStrategyMismatchError,
    ReplacementFailedError,
    ReplacementPriceResolutionError,
    ReplacementScopeError,
    ReplacementValidationError,
    StrategyNotActiveError,
)
from strategy.replacement_models import ReplaceMealRequest
from strategy.replacement_service import MealReplacementService
from strategy.service import StrategyService
from startup_validation import StartupConfigurationError, validate_startup_configuration
from telegram_auth import TelegramAuthData
from pydantic import BaseModel, ConfigDict, Field

from generation_jobs.exceptions import (
    GenerationJobNotFoundError,
    GenerationPrepareError,
)
from generation_jobs.models import (
    ActiveGenerationJobResponse,
    CreateGenerationJobResponse,
    GenerationJobStatusResponse,
    record_to_status_response,
)
from generation_jobs.service import get_generation_job_service
from generation_jobs.worker import get_generation_worker
from dev_tools.consistency import check_user_data_consistency, lifecycle_summary_counts
from dev_tools.fixtures import QaFixtureService
from dev_tools.guards import DevToolsDisabledError, is_dev_tools_enabled
from dev_tools.reset import DevResetService
from dev_tools.scenarios import QA_SCENARIO_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

USER_MESSAGE_TIMEOUT = "Генерация заняла слишком много времени. Попробуйте ещё раз."
USER_MESSAGE_INVALID_MENU = "Не удалось сформировать корректное меню. Попробуйте ещё раз."
USER_MESSAGE_OUTPUT_TRUNCATED = "Не удалось сформировать полное меню. Попробуйте ещё раз."
USER_MESSAGE_UNAVAILABLE = "Сервис генерации временно недоступен."
USER_MESSAGE_STRATEGY_INVALID = "Не удалось сформировать стратегию питания. Проверьте настройки и попробуйте ещё раз."
USER_MESSAGE_STRATEGY_SAVE_FAILED = (
    "Меню создано, но не удалось сохранить стратегию. Попробуйте сгенерировать меню ещё раз."
)
USER_MESSAGE_REPLACE_NOT_FOUND = "Не удалось найти стратегию или блюдо"
USER_MESSAGE_REPLACE_NOT_ACTIVE = "Этот план уже завершён или заменён новым"
USER_MESSAGE_REPLACE_INVALID = "Не удалось заменить блюдо с текущими ограничениями"
USER_MESSAGE_REPLACE_FAILED = "Не удалось подобрать подходящую замену"
USER_MESSAGE_REPLACE_PRICE_UNRESOLVED = (
    "Не удалось рассчитать стоимость продуктов для этого варианта. "
    "Текущий план не изменён. Попробуйте заменить блюдо ещё раз."
)
USER_MESSAGE_CATALOG_REPLACE_NOT_IMPLEMENTED = (
    "Замена блюда для меню из каталога пока недоступна"
)
USER_MESSAGE_CATALOG_REPLACEMENT_NOT_FOUND = (
    "Не удалось найти подходящую замену в каталоге. "
    "Попробуйте другую причину или другое блюдо."
)
USER_MESSAGE_CATALOG_REPLACEMENT_ROUTING_ERROR = (
    "Не удалось определить движок замены для этого меню. "
    "Обновите план и попробуйте снова."
)
USER_MESSAGE_CATALOG_GENERATION_FAILED = (
    "Не удалось составить меню по каталогу рецептов. Попробуйте изменить параметры."
)
USER_MESSAGE_POSITIVE_EVENT_INVALID = "Не удалось сохранить отметку"
USER_MESSAGE_POSITIVE_EVENT_NOT_ALLOWED = "Этот план уже заменён новым, отметки недоступны"
USER_MESSAGE_LEARNING_NOT_FOUND = "Рекомендация не найдена"
USER_MESSAGE_LEARNING_NOT_AVAILABLE = "Эта рекомендация больше недоступна"
USER_MESSAGE_LEARNING_FAILED = "Не удалось обновить рекомендацию"
USER_MESSAGE_LEARNED_PREFERENCE_NOT_FOUND = "Адаптивное предпочтение не найдено"
USER_MESSAGE_LEARNED_PREFERENCE_NOT_AVAILABLE = (
    "Это адаптивное предпочтение больше недоступно"
)
USER_MESSAGE_LEARNED_PREFERENCE_FAILED = (
    "Не удалось обновить адаптивное предпочтение"
)
USER_MESSAGE_MENU_PLAN_NOT_FOUND = "Сохранённое меню не найдено"
USER_MESSAGE_MENU_PLAN_STALE = (
    "Меню изменилось в другой сессии. Обновите план и попробуйте снова."
)
USER_MESSAGE_MENU_PLAN_FAILED = "Не удалось сохранить меню. Попробуйте ещё раз."
USER_MESSAGE_MEMORY_NOT_FOUND = "Отметка памяти не найдена"
USER_MESSAGE_MEMORY_NOT_PROMOTABLE = "Эту отметку нельзя добавить в профиль"
USER_MESSAGE_MEMORY_NOT_CONFIRMED = "Сначала подтвердите отметку"
USER_MESSAGE_MEMORY_PROMOTION_STALE = (
    "Профиль изменился в другой сессии. Обновите данные и попробуйте снова."
)
USER_MESSAGE_MEMORY_PROMOTION_FAILED = "Не удалось добавить в профиль. Попробуйте ещё раз."
USER_MESSAGE_PREVIEW_STALE = "Настройки изменились. Проверьте план ещё раз."
USER_MESSAGE_PREVIEW_EXPIRED = "Срок проверки настроек истёк."
USER_MESSAGE_PREVIEW_INVALID = "Не удалось подтвердить настройки. Проверьте план ещё раз."
USER_MESSAGE_PROFILE_INVALID = "Проверьте настройки профиля и попробуйте ещё раз."
USER_MESSAGE_PROFILE_STALE = "Настройки были изменены в другой сессии."
USER_MESSAGE_PREVIEW_REQUIRED = "Приложение обновилось. Проверьте настройки ещё раз."
USER_MESSAGE_RESOLUTION_FAILED = "Не удалось обновить предпочтение."
USER_MESSAGE_CONFLICT_NOT_FOUND = "Это противоречие уже не актуально."
USER_MESSAGE_RESOLUTION_INVALID_ACTION = "Не удалось применить выбранное действие."
USER_MESSAGE_CONSTRAINT_NOT_REMOVABLE = (
    "Это ограничение можно изменить только в настройках профиля."
)
USER_MESSAGE_BEHAVIOR_NOT_FOUND = "Наблюдение не найдено"
USER_MESSAGE_BEHAVIOR_INVALID_TRANSITION = "Это действие сейчас недоступно"
USER_MESSAGE_BEHAVIOR_NOT_CONFIRMABLE = "Это наблюдение нельзя подтвердить"
USER_MESSAGE_BEHAVIOR_NOT_DISMISSIBLE = "Это наблюдение нельзя отклонить"
USER_MESSAGE_BEHAVIOR_NOT_SNOOZABLE = "Это наблюдение нельзя отложить"
USER_MESSAGE_BEHAVIOR_NOT_REVOKABLE = "Это наблюдение нельзя отозвать"
USER_MESSAGE_BEHAVIOR_SNOOZE_FAILED = "Не удалось отложить наблюдение. Попробуйте ещё раз."
USER_MESSAGE_BEHAVIOR_REVOKE_FAILED = "Не удалось отозвать наблюдение. Попробуйте ещё раз."
USER_MESSAGE_BEHAVIOR_UNAVAILABLE = "Сервис наблюдений временно недоступен"
USER_MESSAGE_BEHAVIOR_RECOMMENDATION_UNAVAILABLE = "Это предложение сейчас недоступно"
USER_MESSAGE_BEHAVIOR_RECOMMENDATION_STALE = (
    "Профиль изменился в другой сессии. Обновите данные и попробуйте снова."
)
USER_MESSAGE_BEHAVIOR_RECOMMENDATION_FAILED = "Не удалось применить предложение. Попробуйте ещё раз."

_strategy_builder = StrategyBuilder()
_strategy_service = StrategyService()
_memory_service = MemoryService()
_memory_promotion_service = MemoryPromotionService()
_behavior_service = BehaviorService()
_preview_service = StrategyPreviewService(_strategy_builder)
_compare_service = StrategyCompareService(
    repository=_strategy_service._repository,
    preview_service=_preview_service,
)
_conflict_resolution_service = ConflictResolutionService(_memory_service)
_replacement_service = MealReplacementService(
    memory_service=_memory_service,
    behavior_service=_behavior_service,
)
_positive_event_service = PositiveEventService(
    strategy_repository=_strategy_service._repository,
)
_learning_service = LearningService(
    strategy_repository=_strategy_service._repository,
    memory_repository=_memory_service._repository,
    behavior_repository=_behavior_service._repository,
)
_trend_service = TrendService()
_menu_plan_service = MenuPlanService()
_plan_delta_service = PlanDeltaService()
_insight_service = InsightService()
_learned_preference_service = LearnedPreferenceService(
    learning_repository=_learning_service._repository,
)
_dev_reset_service = DevResetService()
_qa_fixture_service = QaFixtureService()
_generation_job_service = get_generation_job_service()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        validate_startup_configuration()
    except StartupConfigurationError as exc:
        logger.error("Startup configuration error: %s", exc)
        raise SystemExit(1) from exc

    db_path = await database.init_db()
    logger.info("SQLite initialized (%s)", db_path)
    logger.info(
        "anthropic_http_transport trust_env=%s",
        "true" if config.ANTHROPIC_TRUST_ENV else "false",
    )
    if is_dev_tools_enabled():
        logger.warning(
            "dev_tools_enabled: reset and QA fixtures are available "
            "(ENVIRONMENT=%s)",
            config.ENVIRONMENT,
        )
    worker = get_generation_worker()
    interrupted = await worker.interrupt_running_on_startup()
    if interrupted:
        logger.warning(
            "generation_jobs_marked_interrupted count=%s",
            interrupted,
        )
    await worker.start()
    try:
        yield
    finally:
        await worker.stop()


app = FastAPI(
    title="Meal Planner API",
    lifespan=lifespan,
    responses={
        401: {"model": ApiErrorResponse, "description": "Authentication required"},
        404: {"model": ApiErrorResponse, "description": "Resource not found"},
        409: {"model": ApiErrorResponse, "description": "Conflict / stale state"},
        422: {"model": ApiErrorResponse, "description": "Validation error"},
        428: {"model": ApiErrorResponse, "description": "Preview required"},
        500: {"model": ApiErrorResponse, "description": "Internal error"},
        502: {"model": ApiErrorResponse, "description": "Upstream failure"},
        503: {"model": ApiErrorResponse, "description": "Service unavailable"},
        504: {"model": ApiErrorResponse, "description": "Timeout"},
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = new_request_id()
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


def _request_id(request: Request | None) -> str | None:
    if request is None:
        return None
    return getattr(request.state, "request_id", None)


PROFILE_VALIDATION_MESSAGES = {
    "PROFILE_INVALID": USER_MESSAGE_PROFILE_INVALID,
    "PROFILE_INCOMPLETE": USER_MESSAGE_PROFILE_INVALID,
    "PROFILE_PROTEIN_REQUIRED": "Выберите источник белка, чтобы продолжить.",
    "PROFILE_ANY_WITH_SPECIFIC_PROTEINS": USER_MESSAGE_PROFILE_INVALID,
    "PROFILE_PROTEIN_EXCLUDED": "Предпочтительный белок конфликтует с исключениями профиля.",
    "PROFILE_TOO_MANY_CONSTRAINTS": "Слишком много ограничений. Удалите часть значений.",
    "PROFILE_CONSTRAINT_VALUE_EMPTY": "Укажите продукт для ограничения.",
    "PROFILE_CONSTRAINT_DUPLICATE": "Ограничение с этим продуктом уже добавлено.",
    "PROFILE_CONSTRAINT_ID_INVALID": USER_MESSAGE_PROFILE_INVALID,
}


def _profile_validation_error_response(
    result: ProfileValidationResult, request: Request | None = None
) -> JSONResponse:
    code = result.code or ErrorCodes.PROFILE_INVALID
    message = PROFILE_VALIDATION_MESSAGES.get(code, USER_MESSAGE_PROFILE_INVALID)
    field_errors = []
    if result.field:
        field_errors.append(
            ApiFieldError(field=f"profile.{result.field}", code=code, message=message)
        )
    return api_error_response(
        status_code=422,
        code=code,
        message=message,
        field_errors=field_errors,
        request_id=_request_id(request),
    )


def _persisted_profile_invalid_response(
    result: ProfileValidationResult, request: Request | None = None
) -> JSONResponse:
    logger.info("persisted_profile_invalid code=%s", result.code)
    return api_error_response(
        status_code=422,
        code=result.code or "PERSISTED_PROFILE_INVALID",
        message=USER_MESSAGE_PROFILE_INVALID,
        request_id=_request_id(request),
    )


def _profile_from_payload(
    payload: ProfilePayload,
    *,
    first_name: str = "",
    stored: dict[str, object] | None = None,
) -> dict[str, object]:
    """Builds the persistence dict from a PUT payload.

    Typed constraints are the canonical input; the deprecated raw allergies
    string can only shrink through `legacy_allergies` (classification flow)
    and is otherwise preserved from the stored profile.
    """
    existing_constraints = constraints_from_profile(stored) if stored else []
    constraints = normalize_constraints(
        payload.dietary_constraints, existing=existing_constraints
    )

    if payload.legacy_allergies is not None:
        allergies = serialize_legacy_allergies(payload.legacy_allergies)
    elif stored is not None and isinstance(stored.get("allergies"), str):
        allergies = stored["allergies"]
    else:
        allergies = "нет"

    if payload.cooking_preferences is not None:
        cooking_preferences = {
            "prefer_faster_meals": payload.cooking_preferences.prefer_faster_meals,
        }
    elif stored is not None and isinstance(stored.get("cooking_preferences"), dict):
        cooking_preferences = stored["cooking_preferences"]
    else:
        cooking_preferences = None

    if payload.planning_preferences is not None:
        planning_preferences = {
            "prefer_familiar_meals": payload.planning_preferences.prefer_familiar_meals,
        }
    elif stored is not None and isinstance(stored.get("planning_preferences"), dict):
        planning_preferences = stored["planning_preferences"]
    else:
        planning_preferences = None

    return normalize_profile_for_persistence(
        {
            "first_name": first_name,
            "days": payload.days,
            "budget": payload.budget,
            "meal_types": payload.meal_types,
            "meals_per_day": payload.meals_per_day,
            "persons": payload.persons,
            "proteins": payload.proteins,
            "goal": payload.goal,
            "cooktime": payload.cooktime,
            "allergies": allergies,
            "dietary_constraints": [item.model_dump(mode="json") for item in constraints],
            "cooking_preferences": cooking_preferences,
            "planning_preferences": planning_preferences,
            "store": payload.store,
        }
    )


def _profile_api_view(stored: dict[str, object]) -> tuple[dict[str, object], int]:
    revision = int(stored.get("revision", 1))
    profile = {key: value for key, value in stored.items() if key != "revision"}
    return profile, revision


def _profile_hash_view(profile: dict[str, object]) -> dict[str, object]:
    return normalize_profile_for_persistence(profile)


async def _load_persisted_profile_for_user(user_id: int) -> dict[str, object] | None:
    stored = await database.get_profile(user_id)
    if stored is None:
        return None
    return normalize_profile_for_persistence(stored)


async def _load_memory_context_for_user(user_id: int) -> tuple[StrategyMemoryContext, bool]:
    try:
        confirmed_signals = await _memory_service.get_confirmed_signals(user_id)
        memory_context = build_strategy_memory_context(confirmed_signals)
        logger.info(
            "memory_context_load_success user_id=%s confirmed_signals_count=%s",
            user_id,
            len(confirmed_signals),
        )
        return memory_context, False
    except Exception as exc:
        logger.warning(
            "memory_context_load_failure user_id=%s error_type=%s",
            user_id,
            type(exc).__name__,
        )
        return StrategyMemoryContext.empty(), True


async def _load_behavior_context_for_user(
    user_id: int,
) -> tuple[StrategyBehaviorContext, bool]:
    try:
        confirmed = await _behavior_service.list_confirmed_insights(user_id)
        behavior_context = build_strategy_behavior_context(confirmed)
        logger.info(
            "behavior_context_load_success user_id=%s confirmed_insights_count=%s",
            user_id,
            len(confirmed),
        )
        return behavior_context, False
    except Exception as exc:
        logger.warning(
            "behavior_context_load_failure user_id=%s error_type=%s",
            user_id,
            type(exc).__name__,
        )
        return StrategyBehaviorContext.empty(), True


async def _load_learned_preferences_context_for_user(
    user_id: int,
) -> tuple[LearnedPreferencesContext, bool]:
    enabled = config.ADAPTIVE_PREFERENCES
    if not enabled:
        return LearnedPreferencesContext.empty(enabled=False), False
    try:
        active = await _learned_preference_service.load_active_for_decision(
            user_id
        )
        context = build_learned_preferences_context(active, enabled=enabled)
        logger.info(
            "learned_preferences_loaded enabled=%s active_count=%s "
            "supported_count=%s preference_types=%s",
            enabled,
            len(active),
            len(context.source_preferences),
            [item.preference_type for item in context.source_preferences],
        )
        return context, False
    except Exception as exc:
        logger.warning(
            "learned_preferences_context_load_failure enabled=%s error_type=%s",
            enabled,
            type(exc).__name__,
        )
        return LearnedPreferencesContext.empty(enabled=enabled), True


DEFAULT_PROFILE = {
    "first_name": "",
    "budget": None,
    "days": 5,
    "meal_types": list(DEFAULT_MEAL_TYPES),
    "meals_per_day": len(DEFAULT_MEAL_TYPES),
    "persons": 1,
    "proteins": ["any"],
    "goal": "home",
    "cooktime": "medium",
    "allergies": "нет",
    "dietary_constraints": [],
    "cooking_preferences": None,
    "planning_preferences": None,
    "store": "any",
    "updated_at": None,
}


def _profile_response_from_stored(stored: dict[str, object]) -> ProfileResponse:
    profile, revision = _profile_api_view(stored)
    legacy_constraints = parse_legacy_allergies(profile.get("allergies"))
    requires_review = bool(legacy_constraints)
    return ProfileResponse(
        profile=profile,
        legacy_constraints=legacy_constraints,
        requires_constraint_review=requires_review,
        revision=revision,
        updated_at=str(stored.get("updated_at")) if stored.get("updated_at") else None,
    )


def _domain_error(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict | None = None,
) -> JSONResponse:
    return api_error_response(
        status_code=status_code,
        code=code,
        message=message,
        details=details,
        request_id=_request_id(request),
    )


@app.exception_handler(RequestValidationError)
async def request_validation_handler(request: Request, exc: RequestValidationError):
    field_errors: list[ApiFieldError] = []
    for error in exc.errors():
        location = error.get("loc") or ()
        # Skip the leading "body" segment for stable field paths.
        parts = [str(part) for part in location if part != "body"]
        field_errors.append(
            ApiFieldError(
                field=".".join(parts) if parts else "request",
                code=str(error.get("type") or "invalid"),
                message=str(error.get("msg") or "Invalid value"),
            )
        )
    logger.info("request_validation_error field_count=%s", len(field_errors))
    return api_error_response(
        status_code=422,
        code=ErrorCodes.REQUEST_VALIDATION_ERROR,
        message="Проверьте введённые данные.",
        field_errors=field_errors,
        request_id=_request_id(request),
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Не удалось выполнить запрос."
    codes_by_status = {
        401: ErrorCodes.AUTH_REQUIRED,
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: ErrorCodes.REQUEST_VALIDATION_ERROR,
    }
    return api_error_response(
        status_code=exc.status_code,
        code=codes_by_status.get(exc.status_code, ErrorCodes.INTERNAL_ERROR),
        message=detail,
        request_id=_request_id(request),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = _request_id(request)
    # Full traceback in the server log; the client still gets an opaque 500.
    logger.exception(
        "unhandled_error request_id=%s error_type=%s",
        request_id,
        type(exc).__name__,
    )
    # Never leak internal exception text for 500s.
    response = api_error_response(
        status_code=500,
        code=ErrorCodes.INTERNAL_ERROR,
        message="Внутренняя ошибка сервера. Попробуйте позже.",
        request_id=request_id,
    )
    # Belt-and-suspenders: ensure browser clients can read 500 JSON instead of
    # treating a CORS-blocked error response as a network failure.
    origin = request.headers.get("origin")
    if origin and origin in config.ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


@app.exception_handler(StrategyPreviewStaleError)
async def strategy_preview_stale_handler(request: Request, _exc: StrategyPreviewStaleError):
    return _domain_error(
        request,
        status_code=409,
        code="STRATEGY_PREVIEW_STALE",
        message=USER_MESSAGE_PREVIEW_STALE,
    )


@app.exception_handler(PreviewTokenError)
async def preview_token_error_handler(request: Request, exc: PreviewTokenError):
    messages = {
        "STRATEGY_PREVIEW_EXPIRED": USER_MESSAGE_PREVIEW_EXPIRED,
        "STRATEGY_PREVIEW_INVALID": USER_MESSAGE_PREVIEW_INVALID,
        "STRATEGY_PREVIEW_STALE_PROFILE": USER_MESSAGE_PREVIEW_STALE,
        "STRATEGY_PREVIEW_STALE_MEMORY": USER_MESSAGE_PREVIEW_STALE,
        "STRATEGY_PREVIEW_STALE_BEHAVIOR": USER_MESSAGE_PREVIEW_STALE,
        "STRATEGY_PREVIEW_STALE_LEARNED_PREFERENCES": USER_MESSAGE_PREVIEW_STALE,
        "STRATEGY_PREVIEW_VERSION_MISMATCH": USER_MESSAGE_PREVIEW_REQUIRED,
        "STRATEGY_PREVIEW_TOKEN_MISSING": USER_MESSAGE_PREVIEW_INVALID,
    }
    logger.info("strategy_preview_token_error code=%s", exc.code)
    return _domain_error(
        request,
        status_code=409,
        code=exc.code,
        message=messages.get(exc.code, USER_MESSAGE_PREVIEW_INVALID),
        details={"retryable": True},
    )


@app.exception_handler(StrategyValidationError)
async def strategy_validation_handler(request: Request, exc: StrategyValidationError):
    if config.ENVIRONMENT != "production":
        logger.warning("strategy_validation_error code=%s message=%s", exc.code, str(exc))
    return _domain_error(
        request,
        status_code=422,
        code=getattr(exc, "code", None) or ErrorCodes.STRATEGY_INVALID,
        message=USER_MESSAGE_STRATEGY_INVALID,
    )


@app.exception_handler(StrategyPersistenceError)
async def strategy_persistence_handler(request: Request, exc: StrategyPersistenceError):
    if config.ENVIRONMENT != "production":
        logger.warning("strategy_persistence_error message=%s", str(exc))
    return _domain_error(
        request,
        status_code=503,
        code=ErrorCodes.STRATEGY_SAVE_FAILED,
        message=USER_MESSAGE_STRATEGY_SAVE_FAILED,
    )


@app.exception_handler(UnsupportedStrategyVersionError)
async def unsupported_strategy_version_handler(request: Request, exc: UnsupportedStrategyVersionError):
    if config.ENVIRONMENT != "production":
        logger.warning("unsupported_strategy_version version=%s", exc.version)
    return _domain_error(
        request,
        status_code=503,
        code=ErrorCodes.STRATEGY_VERSION_UNSUPPORTED,
        message=USER_MESSAGE_UNAVAILABLE,
    )


@app.exception_handler(StrategyNotFoundError)
async def strategy_not_found_handler(request: Request, _exc: StrategyNotFoundError):
    return _domain_error(
        request,
        status_code=404,
        code=ErrorCodes.STRATEGY_NOT_FOUND,
        message=USER_MESSAGE_REPLACE_NOT_FOUND,
    )


@app.exception_handler(MemorySignalNotFoundError)
async def memory_signal_not_found_handler(request: Request, _exc: MemorySignalNotFoundError):
    return _domain_error(
        request,
        status_code=404,
        code=ErrorCodes.MEMORY_SIGNAL_NOT_FOUND,
        message=USER_MESSAGE_MEMORY_NOT_FOUND,
    )


@app.exception_handler(BehaviorInsightNotFoundError)
async def behavior_insight_not_found_handler(
    request: Request, _exc: BehaviorInsightNotFoundError
):
    return _domain_error(
        request,
        status_code=404,
        code=ErrorCodes.BEHAVIOR_INSIGHT_NOT_FOUND,
        message=USER_MESSAGE_BEHAVIOR_NOT_FOUND,
    )


@app.exception_handler(BehaviorInsightNotConfirmableError)
async def behavior_insight_not_confirmable_handler(
    request: Request, _exc: BehaviorInsightNotConfirmableError
):
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.BEHAVIOR_INSIGHT_NOT_CONFIRMABLE,
        message=USER_MESSAGE_BEHAVIOR_NOT_CONFIRMABLE,
    )


@app.exception_handler(BehaviorInsightNotDismissibleError)
async def behavior_insight_not_dismissible_handler(
    request: Request, _exc: BehaviorInsightNotDismissibleError
):
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.BEHAVIOR_INSIGHT_NOT_DISMISSIBLE,
        message=USER_MESSAGE_BEHAVIOR_NOT_DISMISSIBLE,
    )


@app.exception_handler(BehaviorInsightNotSnoozableError)
async def behavior_insight_not_snoozable_handler(
    request: Request, _exc: BehaviorInsightNotSnoozableError
):
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.BEHAVIOR_INSIGHT_NOT_SNOOZABLE,
        message=USER_MESSAGE_BEHAVIOR_NOT_SNOOZABLE,
    )


@app.exception_handler(BehaviorInsightNotRevokableError)
async def behavior_insight_not_revokable_handler(
    request: Request, _exc: BehaviorInsightNotRevokableError
):
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.BEHAVIOR_INSIGHT_NOT_REVOKABLE,
        message=USER_MESSAGE_BEHAVIOR_NOT_REVOKABLE,
    )


@app.exception_handler(BehaviorSnoozeFailedError)
async def behavior_snooze_failed_handler(
    request: Request, _exc: BehaviorSnoozeFailedError
):
    return _domain_error(
        request,
        status_code=503,
        code=ErrorCodes.BEHAVIOR_SNOOZE_FAILED,
        message=USER_MESSAGE_BEHAVIOR_SNOOZE_FAILED,
    )


@app.exception_handler(BehaviorRevokeFailedError)
async def behavior_revoke_failed_handler(
    request: Request, _exc: BehaviorRevokeFailedError
):
    return _domain_error(
        request,
        status_code=503,
        code=ErrorCodes.BEHAVIOR_REVOKE_FAILED,
        message=USER_MESSAGE_BEHAVIOR_REVOKE_FAILED,
    )


@app.exception_handler(BehaviorInsightInvalidTransitionError)
async def behavior_insight_invalid_transition_handler(
    request: Request, _exc: BehaviorInsightInvalidTransitionError
):
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.BEHAVIOR_INSIGHT_INVALID_TRANSITION,
        message=USER_MESSAGE_BEHAVIOR_INVALID_TRANSITION,
    )


@app.exception_handler(BehaviorServiceUnavailableError)
async def behavior_service_unavailable_handler(
    request: Request, _exc: BehaviorServiceUnavailableError
):
    logger.warning("behavior_service_unavailable")
    return _domain_error(
        request,
        status_code=503,
        code=ErrorCodes.BEHAVIOR_SERVICE_UNAVAILABLE,
        message=USER_MESSAGE_BEHAVIOR_UNAVAILABLE,
    )


@app.exception_handler(BehaviorEvaluationError)
async def behavior_evaluation_failed_handler(
    request: Request, _exc: BehaviorEvaluationError
):
    logger.warning("behavior_evaluation_failed")
    return _domain_error(
        request,
        status_code=503,
        code=ErrorCodes.BEHAVIOR_EVALUATION_FAILED,
        message=USER_MESSAGE_BEHAVIOR_UNAVAILABLE,
    )


@app.exception_handler(MemorySignalNotPromotableError)
async def memory_signal_not_promotable_handler(
    request: Request, _exc: MemorySignalNotPromotableError
):
    logger.info("memory_promotion_rejected code=%s", _exc.code)
    return _domain_error(
        request,
        status_code=422,
        code=ErrorCodes.MEMORY_SIGNAL_NOT_PROMOTABLE,
        message=USER_MESSAGE_MEMORY_NOT_PROMOTABLE,
    )


@app.exception_handler(MemorySignalNotConfirmedError)
async def memory_signal_not_confirmed_handler(
    request: Request, _exc: MemorySignalNotConfirmedError
):
    return _domain_error(
        request,
        status_code=422,
        code=ErrorCodes.MEMORY_SIGNAL_NOT_CONFIRMED,
        message=USER_MESSAGE_MEMORY_NOT_CONFIRMED,
    )


@app.exception_handler(MemorySignalAlreadyPromotedError)
async def memory_signal_already_promoted_handler(
    request: Request, exc: MemorySignalAlreadyPromotedError
):
    profile_view, _revision = _profile_api_view(exc.profile)
    body = PromoteMemorySignalResponse(
        status="already_promoted",
        profile=profile_view,
        profile_revision=exc.profile_revision,
        signal_status="promoted",
        constraint_id=exc.constraint_id,
    )
    return JSONResponse(status_code=200, content=body.model_dump(mode="json"))


@app.exception_handler(MemoryPromotionProfileStaleError)
async def memory_promotion_stale_handler(request: Request, exc: MemoryPromotionProfileStaleError):
    logger.info(
        "memory_promotion_stale current_revision=%s",
        exc.current_revision,
    )
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.MEMORY_PROMOTION_PROFILE_STALE,
        message=USER_MESSAGE_MEMORY_PROMOTION_STALE,
        details={"current_revision": exc.current_revision},
    )


@app.exception_handler(MemoryPromotionFailedError)
async def memory_promotion_failed_handler(request: Request, _exc: MemoryPromotionFailedError):
    logger.warning("memory_promotion_failed")
    return _domain_error(
        request,
        status_code=500,
        code=ErrorCodes.MEMORY_PROMOTION_FAILED,
        message=USER_MESSAGE_MEMORY_PROMOTION_FAILED,
    )


@app.exception_handler(MealNotFoundError)
async def meal_not_found_handler(request: Request, exc: MealNotFoundError):
    if config.ENVIRONMENT != "production":
        logger.warning("meal_not_found meal_id=%s", exc.meal_id)
    return _domain_error(
        request,
        status_code=404,
        code=ErrorCodes.REPLACEMENT_NOT_FOUND,
        message=USER_MESSAGE_REPLACE_NOT_FOUND,
    )


@app.exception_handler(StrategyNotActiveError)
async def strategy_not_active_handler(request: Request, exc: StrategyNotActiveError):
    if config.ENVIRONMENT != "production":
        logger.warning("strategy_not_active status=%s code=%s", exc.status, exc.code)
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.STRATEGY_NOT_ACTIVE,
        message=USER_MESSAGE_REPLACE_NOT_ACTIVE,
    )


@app.exception_handler(MenuStrategyMismatchError)
@app.exception_handler(ReplacementScopeError)
@app.exception_handler(ReplacementValidationError)
async def replacement_validation_handler(request: Request, exc: Exception):
    if config.ENVIRONMENT != "production":
        code = getattr(exc, "code", "REPLACEMENT_VALIDATION")
        logger.warning("replacement_validation_error code=%s message=%s", code, str(exc))
    return _domain_error(
        request,
        status_code=422,
        code=ErrorCodes.REPLACEMENT_INVALID,
        message=USER_MESSAGE_REPLACE_INVALID,
    )


@app.exception_handler(ReplacementPriceResolutionError)
async def replacement_price_resolution_handler(
    request: Request, exc: ReplacementPriceResolutionError
):
    if config.ENVIRONMENT != "production":
        logger.warning(
            "replacement_price_unresolved_api unresolved_count=%s",
            len(exc.unresolved_items),
        )
    return _domain_error(
        request,
        status_code=422,
        code=ErrorCodes.REPLACEMENT_PRICE_UNRESOLVED,
        message=USER_MESSAGE_REPLACE_PRICE_UNRESOLVED,
        details={"unresolved_count": len(exc.unresolved_items)},
    )


@app.exception_handler(PositiveEventValidationError)
async def positive_event_validation_handler(
    request: Request, exc: PositiveEventValidationError
):
    logger.info("positive_event_rejected reason=validation code=%s", exc.code)
    return _domain_error(
        request,
        status_code=422,
        code=ErrorCodes.POSITIVE_EVENT_INVALID,
        message=USER_MESSAGE_POSITIVE_EVENT_INVALID,
    )


@app.exception_handler(PositiveEventNotAllowedError)
async def positive_event_not_allowed_handler(
    request: Request, _exc: PositiveEventNotAllowedError
):
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.POSITIVE_EVENT_NOT_ALLOWED,
        message=USER_MESSAGE_POSITIVE_EVENT_NOT_ALLOWED,
    )


@app.exception_handler(LearningRecommendationNotFoundError)
async def learning_not_found_handler(
    request: Request, _exc: LearningRecommendationNotFoundError
):
    return _domain_error(
        request,
        status_code=404,
        code=ErrorCodes.LEARNING_RECOMMENDATION_NOT_FOUND,
        message=USER_MESSAGE_LEARNING_NOT_FOUND,
    )


@app.exception_handler(LearningRecommendationTransitionError)
async def learning_transition_handler(
    request: Request, _exc: LearningRecommendationTransitionError
):
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.LEARNING_RECOMMENDATION_NOT_AVAILABLE,
        message=USER_MESSAGE_LEARNING_NOT_AVAILABLE,
    )


@app.exception_handler(LearningPersistenceError)
async def learning_persistence_handler(
    request: Request, _exc: LearningPersistenceError
):
    logger.warning("learning_recommendation_failed")
    return _domain_error(
        request,
        status_code=503,
        code=ErrorCodes.LEARNING_RECOMMENDATION_FAILED,
        message=USER_MESSAGE_LEARNING_FAILED,
    )


@app.exception_handler(LearnedPreferenceNotFoundError)
async def learned_preference_not_found_handler(
    request: Request, _exc: LearnedPreferenceNotFoundError
):
    return _domain_error(
        request,
        status_code=404,
        code=ErrorCodes.LEARNED_PREFERENCE_NOT_FOUND,
        message=USER_MESSAGE_LEARNED_PREFERENCE_NOT_FOUND,
    )


@app.exception_handler(LearnedPreferenceNotAvailableError)
async def learned_preference_not_available_handler(
    request: Request, _exc: LearnedPreferenceNotAvailableError
):
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.LEARNED_PREFERENCE_NOT_AVAILABLE,
        message=USER_MESSAGE_LEARNED_PREFERENCE_NOT_AVAILABLE,
    )


@app.exception_handler(LearnedPreferencePersistenceError)
async def learned_preference_persistence_handler(
    request: Request, _exc: LearnedPreferencePersistenceError
):
    logger.warning("learned_preference_failed")
    return _domain_error(
        request,
        status_code=503,
        code=ErrorCodes.LEARNED_PREFERENCE_FAILED,
        message=USER_MESSAGE_LEARNED_PREFERENCE_FAILED,
    )


@app.exception_handler(MenuPlanNotFoundError)
async def menu_plan_not_found_handler(
    request: Request, _exc: MenuPlanNotFoundError
):
    return _domain_error(
        request,
        status_code=404,
        code=ErrorCodes.MENU_PLAN_NOT_FOUND,
        message=USER_MESSAGE_MENU_PLAN_NOT_FOUND,
    )


@app.exception_handler(MenuPlanConcurrencyError)
async def menu_plan_concurrency_handler(
    request: Request, _exc: MenuPlanConcurrencyError
):
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.MENU_PLAN_STALE,
        message=USER_MESSAGE_MENU_PLAN_STALE,
    )


@app.exception_handler(MenuPlanPersistenceError)
async def menu_plan_persistence_handler(
    request: Request, _exc: MenuPlanPersistenceError
):
    logger.warning("menu_plan_persistence_failed")
    return _domain_error(
        request,
        status_code=503,
        code=ErrorCodes.MENU_PLAN_FAILED,
        message=USER_MESSAGE_MENU_PLAN_FAILED,
    )


@app.exception_handler(ReplacementFailedError)
async def replacement_failed_handler(request: Request, exc: ReplacementFailedError):
    if config.ENVIRONMENT != "production":
        logger.warning(
            "replacement_failed issue_codes=%s issue_count=%s",
            exc.issue_codes,
            len(exc.issue_codes),
        )
    return _domain_error(
        request,
        status_code=502,
        code=ErrorCodes.REPLACEMENT_FAILED,
        message=USER_MESSAGE_REPLACE_FAILED,
    )


@app.exception_handler(CatalogGenerationError)
async def catalog_generation_error_handler(
    request: Request, exc: CatalogGenerationError
):
    if exc.code == CatalogGenerationError.CATALOG_REPLACE_NOT_IMPLEMENTED:
        return _domain_error(
            request,
            status_code=501,
            code=ErrorCodes.CATALOG_REPLACE_NOT_IMPLEMENTED,
            message=USER_MESSAGE_CATALOG_REPLACE_NOT_IMPLEMENTED,
        )
    if exc.code == CatalogGenerationError.CATALOG_REPLACEMENT_NOT_FOUND:
        return _domain_error(
            request,
            status_code=422,
            code=ErrorCodes.CATALOG_REPLACEMENT_NOT_FOUND,
            message=USER_MESSAGE_CATALOG_REPLACEMENT_NOT_FOUND,
            details=exc.details or None,
        )
    if exc.code == CatalogGenerationError.CATALOG_REPLACEMENT_ROUTING_ERROR:
        return _domain_error(
            request,
            status_code=422,
            code=ErrorCodes.CATALOG_REPLACEMENT_ROUTING_ERROR,
            message=USER_MESSAGE_CATALOG_REPLACEMENT_ROUTING_ERROR,
            details=exc.details or None,
        )
    if config.ENVIRONMENT != "production":
        logger.warning(
            "catalog_generation_error code=%s message=%s",
            exc.code,
            exc.message,
        )
    status = 503 if exc.code == CatalogGenerationError.GENERATION_ENGINE_UNAVAILABLE else 422
    return _domain_error(
        request,
        status_code=status,
        code=exc.code,
        message=USER_MESSAGE_CATALOG_GENERATION_FAILED,
        details=exc.details or None,
    )


@app.exception_handler(ClaudeOutputTruncatedError)
async def claude_output_truncated_handler(
    request: Request, exc: ClaudeOutputTruncatedError
):
    logger.exception(
        "menu_output_truncated_502 request_id=%s stop_reason=%s output_tokens=%s raw_chars=%s",
        _request_id(request),
        exc.stop_reason,
        exc.output_tokens,
        exc.raw_chars,
    )
    return _domain_error(
        request,
        status_code=502,
        code=ErrorCodes.MENU_GENERATION_OUTPUT_TRUNCATED,
        message=USER_MESSAGE_OUTPUT_TRUNCATED,
    )


@app.exception_handler(ClaudeTimeoutError)
async def claude_timeout_handler(request: Request, _exc: ClaudeTimeoutError):
    return _domain_error(
        request,
        status_code=504,
        code=ErrorCodes.MENU_GENERATION_TIMEOUT,
        message=USER_MESSAGE_TIMEOUT,
    )


@app.exception_handler(ClaudeUnavailableError)
async def claude_unavailable_handler(request: Request, _exc: ClaudeUnavailableError):
    return _domain_error(
        request,
        status_code=503,
        code=ErrorCodes.MENU_GENERATION_UNAVAILABLE,
        message=USER_MESSAGE_UNAVAILABLE,
    )


@app.exception_handler(ClaudeJsonError)
@app.exception_handler(ClaudeValidationError)
@app.exception_handler(MenuConstraintError)
async def claude_invalid_menu_handler(request: Request, exc: Exception):
    # Never return 502 without the root cause (with traceback) in the log.
    safe_details: dict | None = None
    if isinstance(exc, MenuConstraintError):
        logger.exception(
            "menu_invalid_502 kind=constraint request_id=%s issue_codes=%s issue_count=%s",
            _request_id(request),
            exc.issue_codes,
            len(exc.issue_codes),
        )
        # Safe machine-readable codes only; diagnostics stay in the backend log.
        if exc.issue_codes:
            safe_details = {"issue_codes": sorted(set(exc.issue_codes))[:10]}
    elif isinstance(exc, ClaudeValidationError):
        logger.exception(
            "menu_invalid_502 kind=schema request_id=%s details=%s",
            _request_id(request),
            exc.details[:12],
        )
    else:
        logger.exception(
            "menu_invalid_502 kind=json request_id=%s error=%s",
            _request_id(request),
            str(exc),
        )
    return _domain_error(
        request,
        status_code=502,
        code=ErrorCodes.MENU_GENERATION_INVALID,
        message=USER_MESSAGE_INVALID_MENU,
        details=safe_details,
    )


@app.get("/api/health")
async def health():
    auth_mode = "development" if config.ALLOW_DEV_AUTH else "telegram"
    return {
        "status": "ok",
        "version": config.APP_VERSION,
        "environment": config.ENVIRONMENT,
        "auth_mode": auth_mode,
        "telegram_auth_configured": bool(config.TELEGRAM_BOT_TOKEN),
        "dev_tools": is_dev_tools_enabled(),
        "menu_generation_configured": config.is_claude_configured(),
    }


@app.get("/api/ready")
async def ready(response: Response):
    database_ready = await database.check_database_ready()
    auth_ready = bool(config.TELEGRAM_BOT_TOKEN) or config.ALLOW_DEV_AUTH
    menu_generation = (
        "ready" if config.is_claude_configured() else "not_configured"
    )

    components = {
        "database": "ready" if database_ready else "unavailable",
        "auth": "ready" if auth_ready else "unavailable",
        "menu_generation": menu_generation,
    }

    if not database_ready or not auth_ready:
        status = "not_ready"
        response.status_code = 503
    elif menu_generation != "ready":
        # Read-only screens remain available without Claude.
        status = "degraded"
    else:
        status = "ready"

    return {
        "status": status,
        "components": components,
        # Backward-compatible booleans for existing diagnostics clients.
        "database": database_ready,
        "telegram_auth": auth_ready,
        "claude_configured": config.is_claude_configured(),
    }


class DevResetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    confirm: str = Field(min_length=1, max_length=32)
    mode: str = Field(default="history_only", max_length=32)


class DevQaScenarioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario: str = Field(min_length=1, max_length=64)


@app.post("/api/dev/reset-current-user")
async def api_dev_reset_current_user(
    payload: DevResetRequest,
    request: Request,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    if not is_dev_tools_enabled():
        return _domain_error(
            request,
            status_code=404,
            code=ErrorCodes.DEV_TOOLS_DISABLED,
            message="Development tools are not available.",
        )
    if payload.confirm != "RESET":
        return _domain_error(
            request,
            status_code=422,
            code=ErrorCodes.DEV_RESET_CONFIRM_REQUIRED,
            message='Confirmation required. Send {"confirm":"RESET"}.',
        )
    mode = payload.mode if payload.mode in {"history_only", "full_user"} else None
    if mode is None:
        return _domain_error(
            request,
            status_code=422,
            code=ErrorCodes.REQUEST_VALIDATION_ERROR,
            message='mode must be "history_only" or "full_user".',
        )
    try:
        result = await _dev_reset_service.reset_current_user(
            current_user.user_id, mode=mode  # type: ignore[arg-type]
        )
    except DevToolsDisabledError:
        return _domain_error(
            request,
            status_code=404,
            code=ErrorCodes.DEV_TOOLS_DISABLED,
            message="Development tools are not available.",
        )
    except Exception:
        logger.warning("dev_reset_endpoint_failed")
        return _domain_error(
            request,
            status_code=503,
            code=ErrorCodes.DEV_TOOLS_FAILED,
            message="Не удалось сбросить тестовые данные. Состояние не изменено.",
        )
    return result


@app.post("/api/dev/load-qa-scenario")
async def api_dev_load_qa_scenario(
    payload: DevQaScenarioRequest,
    request: Request,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    if not is_dev_tools_enabled():
        return _domain_error(
            request,
            status_code=404,
            code=ErrorCodes.DEV_TOOLS_DISABLED,
            message="Development tools are not available.",
        )
    if payload.scenario not in QA_SCENARIO_NAMES:
        return _domain_error(
            request,
            status_code=422,
            code=ErrorCodes.DEV_QA_SCENARIO_UNKNOWN,
            message="Unknown QA scenario.",
        )
    try:
        return await _qa_fixture_service.load_scenario(
            current_user.user_id, payload.scenario
        )
    except DevToolsDisabledError:
        return _domain_error(
            request,
            status_code=404,
            code=ErrorCodes.DEV_TOOLS_DISABLED,
            message="Development tools are not available.",
        )
    except Exception:
        logger.warning("dev_qa_scenario_failed scenario=%s", payload.scenario)
        return _domain_error(
            request,
            status_code=503,
            code=ErrorCodes.DEV_TOOLS_FAILED,
            message="Не удалось загрузить QA-сценарий. Попробуйте ещё раз.",
        )


@app.get("/api/dev/diagnostics")
async def api_dev_diagnostics(
    request: Request,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    if not is_dev_tools_enabled():
        return _domain_error(
            request,
            status_code=404,
            code=ErrorCodes.DEV_TOOLS_DISABLED,
            message="Development tools are not available.",
        )
    consistency = await check_user_data_consistency(current_user.user_id)
    counts = await lifecycle_summary_counts(current_user.user_id)
    return {
        "dev_mode": True,
        "version": config.APP_VERSION,
        "environment": config.ENVIRONMENT,
        "auth_mode": "development",
        "adaptive_preferences": config.ADAPTIVE_PREFERENCES,
        "menu_generation_configured": config.is_claude_configured(),
        "consistency": consistency,
        "lifecycle_counts": counts,
        "scenarios": sorted(QA_SCENARIO_NAMES),
    }


@app.post("/api/strategy/preview")
async def api_strategy_preview(
    payload: StrategyPreviewRequest,
    request: Request,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    stored = await database.get_profile(current_user.user_id)
    if stored is None:
        logger.info("preview_without_profile user_id=%s", current_user.user_id)
        return _domain_error(
            request,
            status_code=422,
            code=ErrorCodes.PROFILE_REQUIRED,
            message="Сначала сохраните настройки профиля.",
        )

    persisted_profile = normalize_profile_for_persistence(stored)
    validation = validate_profile_for_generation(persisted_profile)
    if validation.status != "valid":
        return _persisted_profile_invalid_response(validation, request)

    memory_context, memory_unavailable = await _load_memory_context_for_user(
        current_user.user_id
    )
    behavior_context, behavior_unavailable = await _load_behavior_context_for_user(
        current_user.user_id
    )
    learned_context, learned_unavailable = (
        await _load_learned_preferences_context_for_user(
            current_user.user_id
        )
    )
    profile_revision = int(stored.get("revision", 1))
    plan_start_date = (payload.plan_start_date or date.today()).isoformat()
    preview = await _preview_service.build_preview(
        persisted_profile,
        memory_context,
        behavior_context,
        learned_context,
        user_id=current_user.user_id,
        profile_revision=profile_revision,
        plan_start_date=plan_start_date,
        memory_unavailable=memory_unavailable,
        behavior_unavailable=behavior_unavailable,
        learned_preferences_unavailable=learned_unavailable,
    )
    logger.info(
        "strategy_preview_issued user_id=%s plan_start_date=%s",
        current_user.user_id,
        plan_start_date,
    )
    return preview.model_dump(mode="json")


@app.post("/api/strategy/{strategy_id}/compare", response_model=StrategyCompareResponse)
async def api_strategy_compare(
    strategy_id: str,
    payload: StrategyCompareRequest,
    request: Request,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    logger.info(
        "strategy_compare_requested strategy_id=%s user_id=%s",
        strategy_id,
        current_user.user_id,
    )
    stored = await database.get_profile(current_user.user_id)
    if stored is None:
        return _domain_error(
            request,
            status_code=422,
            code=ErrorCodes.PROFILE_REQUIRED,
            message="Сначала сохраните настройки профиля.",
        )

    persisted_profile = normalize_profile_for_persistence(stored)
    validation = validate_profile_for_generation(persisted_profile)
    if validation.status != "valid":
        return _persisted_profile_invalid_response(validation, request)

    memory_context, memory_unavailable = await _load_memory_context_for_user(
        current_user.user_id
    )
    behavior_context, behavior_unavailable = await _load_behavior_context_for_user(
        current_user.user_id
    )
    learned_context, learned_unavailable = (
        await _load_learned_preferences_context_for_user(
            current_user.user_id
        )
    )
    profile_revision = int(stored.get("revision", 1))
    plan_start_date = (payload.plan_start_date or date.today()).isoformat()

    try:
        result = await _compare_service.compare(
            user_id=current_user.user_id,
            strategy_id=strategy_id,
            profile=persisted_profile,
            profile_revision=profile_revision,
            plan_start_date=plan_start_date,
            memory_context=memory_context,
            memory_unavailable=memory_unavailable,
            behavior_context=behavior_context,
            learned_context=learned_context,
            behavior_unavailable=behavior_unavailable,
            learned_preferences_unavailable=learned_unavailable,
        )
    except StrategyNotFoundError:
        raise
    except UnsupportedStrategyVersionError:
        return _domain_error(
            request,
            status_code=422,
            code=ErrorCodes.STRATEGY_COMPARE_UNSUPPORTED_VERSION,
            message="Для этого плана сравнение недоступно.",
        )
    except Exception:
        logger.exception("strategy_compare_failed strategy_id=%s", strategy_id)
        return _domain_error(
            request,
            status_code=503,
            code=ErrorCodes.STRATEGY_COMPARE_FAILED,
            message="Не удалось сравнить настройки планов.",
        )

    return result.model_dump(mode="json")


@app.exception_handler(ConflictNotFoundError)
async def conflict_not_found_handler(request: Request, _exc: ConflictNotFoundError):
    logger.info("conflict_not_found")
    return _domain_error(
        request,
        status_code=409,
        code=ErrorCodes.CONFLICT_NOT_FOUND,
        message=USER_MESSAGE_CONFLICT_NOT_FOUND,
    )


@app.post("/api/strategy/resolve-conflict", response_model=ResolveConflictResponse)
async def api_resolve_strategy_conflict(
    payload: ResolveConflictRequest,
    request: Request,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    memory_context, memory_unavailable = await _load_memory_context_for_user(
        current_user.user_id
    )
    behavior_context, behavior_unavailable = await _load_behavior_context_for_user(
        current_user.user_id
    )
    learned_context, learned_unavailable = (
        await _load_learned_preferences_context_for_user(
            current_user.user_id
        )
    )
    stored = await database.get_profile(current_user.user_id)
    if stored is None:
        return _domain_error(
            request,
            status_code=422,
            code=ErrorCodes.PROFILE_REQUIRED,
            message=USER_MESSAGE_PROFILE_INVALID,
        )

    persisted_profile = normalize_profile_for_persistence(stored)
    profile_revision = int(stored.get("revision", 1))
    validation = validate_profile_for_generation(persisted_profile)
    if validation.status != "valid":
        return _persisted_profile_invalid_response(validation, request)

    try:
        verified = verify_preview_token(
            payload.preview_token,
            user_id=current_user.user_id,
            profile=persisted_profile,
            profile_revision=profile_revision,
            memory_context=memory_context,
            behavior_context=behavior_context,
            learned_context=learned_context,
            memory_unavailable=memory_unavailable,
            behavior_unavailable=behavior_unavailable,
            learned_preferences_unavailable=learned_unavailable,
        )
    except PreviewTokenError as exc:
        raise exc

    try:
        result = await _conflict_resolution_service.resolve(
            user_id=current_user.user_id,
            request=payload,
            profile=persisted_profile,
            profile_revision=profile_revision,
            memory_context=memory_context,
            memory_unavailable=memory_unavailable,
            verified_token=verified,
        )
        return result.model_dump(mode="json")
    except MemorySignalNotFoundError:
        return _domain_error(
            request,
            status_code=404,
            code=ErrorCodes.MEMORY_SIGNAL_NOT_FOUND,
            message=USER_MESSAGE_MEMORY_NOT_FOUND,
        )
    except StrategyValidationError as exc:
        messages = {
            "CONFLICT_ACTION_NOT_ALLOWED": USER_MESSAGE_RESOLUTION_INVALID_ACTION,
            "CONSTRAINT_NOT_REMOVABLE": USER_MESSAGE_CONSTRAINT_NOT_REMOVABLE,
        }
        return _domain_error(
            request,
            status_code=422,
            code=exc.code or ErrorCodes.CONFLICT_RESOLUTION_FAILED,
            message=messages.get(exc.code or "", USER_MESSAGE_RESOLUTION_FAILED),
        )


@app.post("/api/generate-menu")
async def api_generate_menu(
    payload: GenerateMenuRequest,
    request: Request,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    if not payload.preview_token:
        logger.info("generation_without_token user_id=%s", current_user.user_id)
        return _domain_error(
            request,
            status_code=428,
            code=ErrorCodes.STRATEGY_PREVIEW_REQUIRED,
            message=USER_MESSAGE_PREVIEW_REQUIRED,
        )

    memory_context, memory_unavailable = await _load_memory_context_for_user(
        current_user.user_id
    )
    behavior_context, behavior_unavailable = await _load_behavior_context_for_user(
        current_user.user_id
    )
    learned_context, learned_unavailable = (
        await _load_learned_preferences_context_for_user(
            current_user.user_id
        )
    )

    stored = await database.get_profile(current_user.user_id)
    if stored is None:
        logger.info("generation_without_profile user_id=%s", current_user.user_id)
        return _domain_error(
            request,
            status_code=422,
            code=ErrorCodes.PROFILE_REQUIRED,
            message=USER_MESSAGE_PROFILE_INVALID,
        )

    persisted_profile = normalize_profile_for_persistence(stored)
    profile_revision = int(stored.get("revision", 1))
    validation = validate_profile_for_generation(persisted_profile)
    if validation.status != "valid":
        return _persisted_profile_invalid_response(validation, request)

    verified = verify_preview_token(
        payload.preview_token,
        user_id=current_user.user_id,
        profile=persisted_profile,
        profile_revision=profile_revision,
        memory_context=memory_context,
        behavior_context=behavior_context,
        learned_context=learned_context,
        memory_unavailable=memory_unavailable,
        behavior_unavailable=behavior_unavailable,
        learned_preferences_unavailable=learned_unavailable,
    )
    plan_start_date = date.fromisoformat(verified.payload.plan_start_date)
    logger.info(
        "strategy_preview_token_verified user_id=%s plan_start_date=%s",
        current_user.user_id,
        plan_start_date.isoformat(),
    )

    profile = persisted_profile
    blocking, _ = detect_strategy_conflicts(
        ProfileContext.from_profile(profile),
        memory_context,
    )
    if blocking:
        raise StrategyValidationError(
            "Blocking strategy conflict detected after preview",
            code="STRATEGY_CONFLICT_AFTER_PREVIEW",
        )

    if learned_context.enabled:
        build_result = _strategy_builder.build_with_reasons_from_inputs(
            profile, memory_context, behavior_context, learned_context
        )
    else:
        # Exact Sprint 9.1 resolver path while adaptive planning is disabled.
        build_result = _strategy_builder.build_with_reasons_from_inputs(
            profile, memory_context, behavior_context
        )
    strategy = build_result.strategy
    reason_codes = build_result.reason_codes
    applied_memory = build_result.applied_memory
    applied_cooking_preference = build_result.applied_cooking_preference
    applied_behavior = build_result.applied_behavior
    applied_planning_preferences = build_result.applied_planning_preferences
    applied_learned_preferences = build_result.applied_learned_preferences
    if applied_learned_preferences is not None:
        applied_types = [
            item.preference_type
            for item in applied_learned_preferences.decisions
            if item.applied
        ]
        skipped_profile_count = sum(
            1
            for item in applied_learned_preferences.decisions
            if item.reason_code
            in {
                "LEARNED_PREFERENCE_IGNORED_PROFILE_PRIORITY",
                "LEARNED_PREFERENCE_REDUNDANT_WITH_PROFILE",
            }
        )
        logger.info(
            "learned_preferences_applied enabled=%s applied_count=%s "
            "preference_types=%s",
            applied_learned_preferences.enabled,
            len(applied_types),
            applied_types,
        )
        if skipped_profile_count:
            logger.info(
                "learned_preferences_skipped_profile_priority count=%s",
                skipped_profile_count,
            )
    decision_context = build_result.decision_context
    decision_trace = build_result.decision_trace

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

    meal_types = list(strategy.meal_types)
    meals_per_day = strategy.meals_per_day

    logger.info(
        "menu_generation_request days=%s meal_types=%s strategy_version=%s user_id=%s",
        strategy.days,
        meal_types,
        strategy.strategy_version,
        current_user.user_id,
    )

    planner_input = build_planner_input(
        strategy=strategy,
        persons=profile.get("persons"),
        proteins=profile.get("proteins"),
        cooktime=profile.get("cooktime"),
        allergies=profile.get("allergies"),
        store=profile.get("store"),
    )

    result = await generate_menu(
        **planner_input.as_generate_menu_kwargs(),
        user_id=current_user.user_id,
        plan_start_date=plan_start_date,
    )

    resolved_start = plan_start_date
    if isinstance(result.get("plan_start_date"), str):
        resolved_start = date.fromisoformat(result["plan_start_date"])

    # Sprint 7.2: the fully validated plan becomes a durable immutable
    # snapshot, committed in the same transaction as the strategy.
    try:
        durable_plan = MenuPlan.model_validate(result)
    except ValueError as exc:
        details: list[str] = []
        if hasattr(exc, "errors"):
            try:
                details = [
                    f"{'.'.join(str(part) for part in err.get('loc', ()))}: {err.get('msg', 'invalid')}"
                    for err in exc.errors()[:12]
                ]
            except Exception:
                details = [str(exc)]
        else:
            details = [str(exc)]
        logger.exception(
            "menu_plan_snapshot_validation_failed user_id=%s details=%s",
            current_user.user_id,
            details,
        )
        raise ClaudeValidationError(
            "Menu plan snapshot validation failed",
            details=details,
        ) from exc
    menu_plan_id = str(uuid.uuid4())

    logger.info(
        "menu_save_started user_id=%s menu_plan_id=%s",
        current_user.user_id,
        menu_plan_id,
    )
    try:
        strategy_id = await _strategy_service.save_active_strategy(
            user_id=current_user.user_id,
            strategy=strategy,
            plan_start_date=resolved_start,
            reason_codes=reason_codes,
            applied_memory=applied_memory,
            applied_cooking_preference=applied_cooking_preference,
            applied_behavior=applied_behavior,
            applied_planning_preferences=applied_planning_preferences,
            applied_learned_preferences=applied_learned_preferences,
            decision_context=decision_context,
            decision_trace=decision_trace,
            menu_plan_id=menu_plan_id,
            menu_plan_json=durable_plan.model_dump_json(),
        )
    except Exception:
        logger.exception(
            "menu_save_failed user_id=%s menu_plan_id=%s",
            current_user.user_id,
            menu_plan_id,
        )
        raise
    logger.info(
        "menu_save_completed user_id=%s menu_plan_id=%s strategy_id=%s",
        current_user.user_id,
        menu_plan_id,
        strategy_id,
    )
    result["strategy_id"] = strategy_id
    result["menu_plan_id"] = menu_plan_id
    result["menu_plan_revision"] = 1
    logger.info(
        "learned_preferences_snapshot_saved enabled=%s decision_count=%s",
        bool(
            applied_learned_preferences
            and applied_learned_preferences.enabled
        ),
        len(applied_learned_preferences.decisions)
        if applied_learned_preferences
        else 0,
    )

    logger.info(
        "menu_generation_success user_id=%s strategy_id=%s menu_plan_id=%s "
        "plan_start_date=%s",
        current_user.user_id,
        strategy_id,
        menu_plan_id,
        resolved_start.isoformat(),
    )
    return result


@app.post(
    "/api/generation-jobs",
    response_model=CreateGenerationJobResponse,
    status_code=202,
)
async def api_create_generation_job(
    payload: GenerateMenuRequest,
    request: Request,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    """Start an async menu generation job (Sprint 10.6)."""
    if not payload.preview_token:
        logger.info("generation_job_without_token user_id=%s", current_user.user_id)
        return _domain_error(
            request,
            status_code=428,
            code=ErrorCodes.STRATEGY_PREVIEW_REQUIRED,
            message=USER_MESSAGE_PREVIEW_REQUIRED,
        )

    try:
        record = await _generation_job_service.create_job(
            user_id=current_user.user_id,
            preview_token=payload.preview_token,
        )
    except GenerationPrepareError as exc:
        if exc.validation_result is not None:
            return _persisted_profile_invalid_response(exc.validation_result, request)
        return _domain_error(
            request,
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
        )

    return JSONResponse(
        status_code=202,
        content=CreateGenerationJobResponse(
            job_id=record.job_id,
            status=record.status,
        ).model_dump(mode="json"),
    )


@app.get(
    "/api/generation-jobs/active",
    response_model=ActiveGenerationJobResponse,
)
async def api_get_active_generation_job(
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    record = await _generation_job_service.get_active(current_user.user_id)
    return ActiveGenerationJobResponse(
        job=record_to_status_response(record) if record is not None else None
    )


@app.get(
    "/api/generation-jobs/{job_id}",
    response_model=GenerationJobStatusResponse,
)
async def api_get_generation_job(
    job_id: str,
    request: Request,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    try:
        record = await _generation_job_service.get_job(job_id, current_user.user_id)
    except GenerationJobNotFoundError:
        return _domain_error(
            request,
            status_code=404,
            code=ErrorCodes.GENERATION_JOB_NOT_FOUND,
            message="Задача генерации не найдена",
        )
    return record_to_status_response(record)


@app.get("/api/strategy/current")
async def api_get_current_strategy(
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    return await _strategy_service.get_current_strategy(current_user.user_id)


@app.get("/api/strategy/{strategy_id}")
async def api_get_strategy_by_id(
    strategy_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    return await _strategy_service.get_strategy_by_id(strategy_id, current_user.user_id)


@app.post("/api/strategy/{strategy_id}/events", response_model=PositiveEventResponse)
async def api_record_positive_event(
    strategy_id: str,
    payload: PositiveEventRequest,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    result = await _positive_event_service.record_positive_event(
        user_id=current_user.user_id,
        strategy_id=strategy_id,
        event_type=payload.event_type,
        meal_id=payload.meal_id,
    )
    return PositiveEventResponse(
        recorded=result.recorded,
        deduplicated=result.deduplicated,
    )


@app.delete(
    "/api/strategy/{strategy_id}/events",
    response_model=PositiveEventUndoResponse,
)
async def api_undo_positive_event(
    strategy_id: str,
    payload: PositiveEventRequest,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    result = await _positive_event_service.undo_positive_event(
        user_id=current_user.user_id,
        strategy_id=strategy_id,
        event_type=payload.event_type,
        meal_id=payload.meal_id,
    )
    return PositiveEventUndoResponse(removed=result.removed, absent=result.absent)


@app.get("/api/menu/current")
async def api_get_current_menu_plan(
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    """Authoritative current MenuPlan (latest validated revision)."""
    return await _menu_plan_service.get_current(current_user.user_id)


@app.get("/api/menu/history")
async def api_get_menu_history(
    request: Request,
    cursor: str | None = None,
    limit: int = DEFAULT_HISTORY_PAGE_SIZE,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    """Paginated compact history of durable plans (Sprint 7.3).

    Summaries only: full plan JSON never appears in the list payload.
    """
    decoded = None
    if cursor is not None:
        decoded = decode_history_cursor(cursor)
        if decoded is None:
            return _domain_error(
                request,
                status_code=422,
                code=ErrorCodes.REQUEST_VALIDATION_ERROR,
                message="Некорректный курсор истории",
            )
    return await _menu_plan_service.get_history(
        current_user.user_id, cursor=decoded, limit=limit
    )


@app.get("/api/menu/{menu_plan_id}/original")
async def api_get_menu_plan_original(
    menu_plan_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    """Immutable initial snapshot as generated (revision 1)."""
    return await _menu_plan_service.get_original(menu_plan_id, current_user.user_id)


@app.get("/api/menu/{menu_plan_id}/delta")
async def api_get_menu_plan_delta(
    menu_plan_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    """Factual differences between the original snapshot and the current
    revision (Sprint 7.4). Aggregate-only; read-only."""
    return await _plan_delta_service.get_delta(menu_plan_id, current_user.user_id)


@app.get("/api/menu/{menu_plan_id}")
async def api_get_menu_plan_by_id(
    menu_plan_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    return await _menu_plan_service.get_by_id(menu_plan_id, current_user.user_id)


@app.post("/api/menu/replace-meal")
async def api_replace_meal(
    payload: ReplaceMealRequest,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    result = await _replacement_service.replace_meal(payload, user_id=current_user.user_id)
    return result.model_dump(mode="json")


@app.get("/api/memory/signals")
async def api_list_memory_signals(
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    signals = await _memory_service.list_signals(current_user.user_id)
    return {"signals": [signal.model_dump() for signal in signals]}


@app.get(
    "/api/learning/recommendations",
    response_model=LearningRecommendationSummary,
)
async def api_list_learning_recommendations(
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    return await _learning_service.list_recommendations(current_user.user_id)


@app.post(
    "/api/learning/recommendations/{recommendation_id}/accept",
    response_model=LearningAcceptResponse,
)
async def api_accept_learning_recommendation(
    recommendation_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    # Human acceptance returns a patch. It intentionally does not mutate Profile.
    return await _learning_service.accept(
        current_user.user_id, recommendation_id
    )


@app.post(
    "/api/learning/recommendations/{recommendation_id}/dismiss",
    response_model=LearningDismissResponse,
)
async def api_dismiss_learning_recommendation(
    recommendation_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    return await _learning_service.dismiss(
        current_user.user_id, recommendation_id
    )


@app.get(
    "/api/learned-preferences",
    response_model=LearnedPreferencesResponse,
)
async def api_list_learned_preferences(
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    """Read-only view of adaptive preferences. Never influences planning."""
    return await _learned_preference_service.list_preferences(
        current_user.user_id
    )


@app.post(
    "/api/learned-preferences/{preference_id}/accept",
    response_model=LearnedPreferencesResponse,
)
async def api_accept_learned_preference(
    preference_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    # Explicit human acceptance is the only way a learned preference is created.
    return await _learned_preference_service.accept(
        current_user.user_id, preference_id
    )


@app.post(
    "/api/learned-preferences/{preference_id}/revoke",
    response_model=LearnedPreferencesResponse,
)
async def api_revoke_learned_preference(
    preference_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    return await _learned_preference_service.revoke(
        current_user.user_id, preference_id
    )


@app.post(
    "/api/learned-preferences/{preference_id}/dismiss-review",
    response_model=LearnedPreferencesResponse,
)
async def api_dismiss_learned_preference_review(
    preference_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    """Persist 'keep active' for the current evidence cohort. No planning side effects."""
    return await _learned_preference_service.dismiss_review(
        current_user.user_id, preference_id
    )


@app.get("/api/trends/summary", response_model=TrendSummaryResponse)
async def api_get_trend_summary(
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    """Read-only long-term trends. Never feeds back into decisions."""
    return await _trend_service.get_trend_summary(current_user.user_id)


@app.get("/api/insights/summary", response_model=InsightSummaryResponse)
async def api_get_insight_summary(
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    """Deterministic knowledge summary; read-only and non-LLM."""
    return await _insight_service.get_summary(current_user.user_id)


@app.get("/api/behavior/insights", response_model=BehaviorInsightsListResponse)
async def api_list_behavior_insights(
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    return await _behavior_service.list_active_insights(current_user.user_id)


@app.post("/api/behavior/insights/{insight_id}/confirm", response_model=BehaviorInsightActionResponse)
async def api_confirm_behavior_insight(
    insight_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    return await _behavior_service.confirm_insight(current_user.user_id, insight_id)


@app.post("/api/behavior/insights/{insight_id}/dismiss", response_model=BehaviorInsightActionResponse)
async def api_dismiss_behavior_insight(
    insight_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    return await _behavior_service.dismiss_insight(current_user.user_id, insight_id)


@app.post("/api/behavior/insights/{insight_id}/snooze", response_model=BehaviorInsightActionResponse)
async def api_snooze_behavior_insight(
    insight_id: str,
    payload: BehaviorSnoozeRequest,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    return await _behavior_service.snooze_insight(
        current_user.user_id,
        insight_id,
        duration=payload.duration,
    )


@app.post("/api/behavior/insights/{insight_id}/revoke", response_model=BehaviorRevokeResponse)
async def api_revoke_behavior_insight(
    insight_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    return await _behavior_service.revoke_insight(current_user.user_id, insight_id)


@app.post(
    "/api/behavior/insights/{insight_id}/apply-recommendation",
    response_model=ApplyBehaviorRecommendationResponse,
)
async def api_apply_behavior_recommendation(
    insight_id: str,
    payload: ApplyBehaviorRecommendationRequest,
    request: Request,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    try:
        return await _behavior_service.apply_recommendation(
            current_user.user_id,
            insight_id,
            expected_revision=payload.expected_profile_revision,
        )
    except BehaviorInsightNotFoundError:
        return _domain_error(
            request,
            status_code=404,
            code=ErrorCodes.BEHAVIOR_INSIGHT_NOT_FOUND,
            message=USER_MESSAGE_BEHAVIOR_NOT_FOUND,
        )
    except BehaviorRecommendationNotAvailableError:
        return _domain_error(
            request,
            status_code=409,
            code=ErrorCodes.BEHAVIOR_RECOMMENDATION_NOT_AVAILABLE,
            message=USER_MESSAGE_BEHAVIOR_RECOMMENDATION_UNAVAILABLE,
        )
    except BehaviorRecommendationProfileStaleError as exc:
        return _domain_error(
            request,
            status_code=409,
            code=ErrorCodes.BEHAVIOR_RECOMMENDATION_PROFILE_STALE,
            message=USER_MESSAGE_BEHAVIOR_RECOMMENDATION_STALE,
            details={"current_revision": exc.current_revision},
        )
    except BehaviorRecommendationFailedError:
        return _domain_error(
            request,
            status_code=503,
            code=ErrorCodes.BEHAVIOR_RECOMMENDATION_FAILED,
            message=USER_MESSAGE_BEHAVIOR_RECOMMENDATION_FAILED,
        )


@app.post("/api/memory/signals/{signal_id}/confirm")
async def api_confirm_memory_signal(
    signal_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    signal = await _memory_service.confirm_signal(current_user.user_id, signal_id)
    return {"signal": signal.model_dump()}


@app.delete("/api/memory/signals/{signal_id}")
async def api_dismiss_memory_signal(
    signal_id: str,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    await _memory_service.dismiss_signal(current_user.user_id, signal_id)
    return {"status": "dismissed", "id": signal_id}


@app.post("/api/memory/signals/{signal_id}/promote", response_model=PromoteMemorySignalResponse)
async def api_promote_memory_signal(
    signal_id: str,
    payload: PromoteMemorySignalRequest,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    logger.info(
        "memory_promotion_attempted user_id=%s signal_type=avoid_ingredient",
        current_user.user_id,
    )
    result = await _memory_promotion_service.promote_signal(
        user_id=current_user.user_id,
        signal_id=signal_id,
        expected_revision=payload.expected_profile_revision,
    )
    profile_view, _revision = _profile_api_view(result.profile)
    return PromoteMemorySignalResponse(
        status=result.status,
        profile=profile_view,
        profile_revision=result.profile_revision,
        signal_status="promoted",
        constraint_id=result.constraint_id,
    ).model_dump(mode="json")


def _default_profile_for_user(current_user: TelegramAuthData) -> dict[str, object]:
    return {
        "user_id": current_user.user_id,
        "first_name": current_user.first_name,
        **DEFAULT_PROFILE,
    }


@app.get("/api/profile", response_model=ProfileResponse)
async def api_get_profile_rest(
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    stored = await database.get_profile(current_user.user_id)
    if stored is None:
        default_profile = _default_profile_for_user(current_user)
        return ProfileResponse(
            profile=default_profile,
            legacy_constraints=[],
            requires_constraint_review=False,
            revision=0,
            updated_at=None,
        ).model_dump(mode="json")

    return _profile_response_from_stored(stored).model_dump(mode="json")


@app.put("/api/profile", response_model=ProfileResponse)
async def api_put_profile(
    payload: UpdateProfileRequest,
    request: Request,
    current_user: TelegramAuthData = Depends(get_current_telegram_user),
):
    first_name = (payload.first_name or current_user.first_name or "").strip()
    stored = await database.get_profile(current_user.user_id)
    try:
        profile_dict = _profile_from_payload(payload, first_name=first_name, stored=stored)
    except DietaryConstraintError as exc:
        logger.info(
            "profile_constraint_error user_id=%s code=%s",
            current_user.user_id,
            exc.code,
        )
        return api_error_response(
            status_code=422,
            code=exc.code,
            message=PROFILE_VALIDATION_MESSAGES.get(exc.code, USER_MESSAGE_PROFILE_INVALID),
            field_errors=[
                ApiFieldError(
                    field=f"profile.{exc.field}",
                    code=exc.code,
                    message=PROFILE_VALIDATION_MESSAGES.get(exc.code, USER_MESSAGE_PROFILE_INVALID),
                )
            ],
            request_id=_request_id(request),
        )

    validation = validate_profile_payload(profile_dict)
    if validation.status != "valid":
        logger.info(
            "profile_validation_error user_id=%s code=%s",
            current_user.user_id,
            validation.code,
        )
        return _profile_validation_error_response(validation, request)

    result = await database.save_profile_with_revision(
        current_user.user_id,
        profile_dict,
        payload.expected_revision,
    )
    if result.stale:
        current_profile, current_revision = _profile_api_view(result.current_profile or {})
        logger.info(
            "profile_stale_conflict user_id=%s expected_revision=%s current_revision=%s",
            current_user.user_id,
            payload.expected_revision,
            current_revision,
        )
        return api_error_response(
            status_code=409,
            code=ErrorCodes.PROFILE_STALE,
            message=USER_MESSAGE_PROFILE_STALE,
            details={
                "current_profile": current_profile,
                "current_revision": current_revision or 0,
            },
            request_id=_request_id(request),
        )

    saved = result.profile or profile_dict
    constraints = constraints_from_profile(saved)
    legacy_count = len(parse_legacy_allergies(saved.get("allergies")))
    logger.info(
        "profile_saved user_id=%s revision=%s constraint_kinds=%s legacy_constraints_count=%s",
        current_user.user_id,
        int(saved.get("revision", 1)),
        constraint_counts_by_kind(constraints),
        legacy_count,
    )
    return _profile_response_from_stored(saved).model_dump(mode="json")

