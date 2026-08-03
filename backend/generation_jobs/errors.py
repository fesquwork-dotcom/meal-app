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

SAFE_MESSAGE_TIMEOUT = "Генерация заняла слишком много времени. Попробуйте ещё раз."
SAFE_MESSAGE_UNAVAILABLE = "Сервис генерации временно недоступен."
SAFE_MESSAGE_INVALID = "Не удалось составить корректное меню. Попробуйте ещё раз."
SAFE_MESSAGE_TRUNCATED = "Не удалось сформировать полное меню. Попробуйте ещё раз."
SAFE_MESSAGE_INTERRUPTED = "Генерация была прервана. Запустите её ещё раз."
SAFE_MESSAGE_FAILED = "Не удалось создать меню. Попробуйте ещё раз."
SAFE_MESSAGE_SAVE_FAILED = "Не удалось сохранить меню. Попробуйте ещё раз."

ERROR_CODE_TIMEOUT = "MENU_GENERATION_TIMEOUT"
ERROR_CODE_UNAVAILABLE = "MENU_GENERATION_UNAVAILABLE"
ERROR_CODE_INVALID = "MENU_GENERATION_INVALID"
ERROR_CODE_TRUNCATED = "MENU_GENERATION_OUTPUT_TRUNCATED"
ERROR_CODE_INTERRUPTED = "GENERATION_INTERRUPTED"
ERROR_CODE_FAILED = "GENERATION_FAILED"
ERROR_CODE_SAVE_FAILED = "GENERATION_SAVE_FAILED"


def map_generation_exception(exc: BaseException) -> tuple[str, str]:
    """Map an exception to (error_code, safe_message) without leaking internals."""
    if isinstance(exc, ClaudeTimeoutError):
        return ERROR_CODE_TIMEOUT, SAFE_MESSAGE_TIMEOUT
    if isinstance(exc, ClaudeUnavailableError):
        return ERROR_CODE_UNAVAILABLE, SAFE_MESSAGE_UNAVAILABLE
    if isinstance(exc, ClaudeOutputTruncatedError):
        return ERROR_CODE_TRUNCATED, SAFE_MESSAGE_TRUNCATED
    if isinstance(
        exc, (ClaudeJsonError, ClaudeValidationError, MenuConstraintError)
    ):
        return ERROR_CODE_INVALID, SAFE_MESSAGE_INVALID
    return ERROR_CODE_FAILED, SAFE_MESSAGE_FAILED
