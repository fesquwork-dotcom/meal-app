"""Safe user-facing error mapping for failed generation jobs."""

from __future__ import annotations

from claude_exceptions import (
    ClaudeJsonError,
    ClaudeOutputTruncatedError,
    ClaudeTimeoutError,
    ClaudeUnavailableError,
    ClaudeValidationError,
    MenuConstraintError,
)
from menu_generation.errors import CatalogGenerationError

SAFE_MESSAGE_TIMEOUT = "Генерация заняла слишком много времени. Попробуйте ещё раз."
SAFE_MESSAGE_UNAVAILABLE = "Сервис генерации временно недоступен."
SAFE_MESSAGE_INVALID = "Не удалось составить корректное меню. Попробуйте ещё раз."
SAFE_MESSAGE_TRUNCATED = "Не удалось сформировать полное меню. Попробуйте ещё раз."
SAFE_MESSAGE_INTERRUPTED = "Генерация была прервана. Запустите её ещё раз."
SAFE_MESSAGE_FAILED = "Не удалось создать меню. Попробуйте ещё раз."
SAFE_MESSAGE_SAVE_FAILED = "Не удалось сохранить меню. Попробуйте ещё раз."
SAFE_MESSAGE_CATALOG_NO_PLAN = (
    "Не удалось составить меню по каталогу рецептов. Попробуйте изменить параметры."
)
SAFE_MESSAGE_CATALOG_PARTIAL = (
    "Не удалось заполнить все приёмы пищи. Попробуйте изменить параметры."
)
SAFE_MESSAGE_CATALOG_REPLACE = (
    "Замена блюда для меню из каталога пока недоступна."
)

ERROR_CODE_TIMEOUT = "MENU_GENERATION_TIMEOUT"
ERROR_CODE_UNAVAILABLE = "MENU_GENERATION_UNAVAILABLE"
ERROR_CODE_INVALID = "MENU_GENERATION_INVALID"
ERROR_CODE_TRUNCATED = "MENU_GENERATION_OUTPUT_TRUNCATED"
ERROR_CODE_INTERRUPTED = "GENERATION_INTERRUPTED"
ERROR_CODE_FAILED = "GENERATION_FAILED"
ERROR_CODE_SAVE_FAILED = "GENERATION_SAVE_FAILED"


_CATALOG_CODE_TO_SAFE: dict[str, tuple[str, str]] = {
    CatalogGenerationError.PLANNER_NO_PLAN: (
        CatalogGenerationError.PLANNER_NO_PLAN,
        SAFE_MESSAGE_CATALOG_NO_PLAN,
    ),
    CatalogGenerationError.PLANNER_PARTIAL_PLAN: (
        CatalogGenerationError.PLANNER_PARTIAL_PLAN,
        SAFE_MESSAGE_CATALOG_PARTIAL,
    ),
    CatalogGenerationError.GENERATION_ENGINE_UNAVAILABLE: (
        ERROR_CODE_UNAVAILABLE,
        SAFE_MESSAGE_UNAVAILABLE,
    ),
    CatalogGenerationError.CATALOG_REPLACE_NOT_IMPLEMENTED: (
        CatalogGenerationError.CATALOG_REPLACE_NOT_IMPLEMENTED,
        SAFE_MESSAGE_CATALOG_REPLACE,
    ),
    CatalogGenerationError.MENUPLAN_VALIDATION_FAILED: (
        ERROR_CODE_INVALID,
        SAFE_MESSAGE_INVALID,
    ),
    CatalogGenerationError.PLANNER_VALIDATION_FAILED: (
        ERROR_CODE_INVALID,
        SAFE_MESSAGE_INVALID,
    ),
    CatalogGenerationError.BASKET_BUILD_FAILED: (
        ERROR_CODE_INVALID,
        SAFE_MESSAGE_INVALID,
    ),
    CatalogGenerationError.MENUPLAN_ADAPTER_FAILED: (
        ERROR_CODE_INVALID,
        SAFE_MESSAGE_INVALID,
    ),
    CatalogGenerationError.CATALOG_RECIPE_NOT_FOUND: (
        ERROR_CODE_INVALID,
        SAFE_MESSAGE_INVALID,
    ),
}


def map_generation_exception(exc: BaseException) -> tuple[str, str]:
    """Map an exception to (error_code, safe_message) without leaking internals."""
    if isinstance(exc, ClaudeTimeoutError):
        return ERROR_CODE_TIMEOUT, SAFE_MESSAGE_TIMEOUT
    if isinstance(exc, ClaudeUnavailableError):
        return ERROR_CODE_UNAVAILABLE, SAFE_MESSAGE_UNAVAILABLE
    if isinstance(exc, ClaudeOutputTruncatedError):
        return ERROR_CODE_TRUNCATED, SAFE_MESSAGE_TRUNCATED
    if isinstance(exc, CatalogGenerationError):
        mapped = _CATALOG_CODE_TO_SAFE.get(exc.code)
        if mapped is not None:
            return mapped
        return ERROR_CODE_FAILED, SAFE_MESSAGE_FAILED
    if isinstance(
        exc, (ClaudeJsonError, ClaudeValidationError, MenuConstraintError)
    ):
        return ERROR_CODE_INVALID, SAFE_MESSAGE_INVALID
    return ERROR_CODE_FAILED, SAFE_MESSAGE_FAILED
