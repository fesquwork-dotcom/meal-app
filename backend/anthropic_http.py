"""Shared Anthropic HTTP transport and safe provider-error parsing (hotfix).

One factory for all api.anthropic.com calls so main generation and meal
replacement share the same proxy/trust contract. The factory owns transport
only — API keys and headers stay at the call sites.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

import config

_DEFAULT_TIMEOUT_SECONDS = 180.0

_MAX_PROVIDER_MESSAGE_LENGTH = 500

# Known Anthropic error types; anything else is reduced to sanitized text.
_KNOWN_ERROR_TYPES = frozenset(
    {
        "invalid_request_error",
        "authentication_error",
        "permission_error",
        "not_found_error",
        "request_too_large",
        "rate_limit_error",
        "api_error",
        "overloaded_error",
        "timeout_error",
    }
)

_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f]")

# Transient provider statuses: retry with backoff inside the existing attempt budget.
RETRYABLE_ANTHROPIC_STATUS_CODES = frozenset({429, 502, 503, 504, 529})

# Delay after a failed attempt N before the next try (attempt is 1-based).
_BACKOFF_SECONDS_BY_ATTEMPT: dict[int, float] = {1: 5.0, 2: 10.0, 3: 20.0}
_MAX_RETRY_AFTER_SECONDS = 30.0


def is_retryable_anthropic_status(status_code: int) -> bool:
    return status_code in RETRYABLE_ANTHROPIC_STATUS_CODES


def parse_retry_after_seconds(response: httpx.Response) -> float | None:
    """Parse Retry-After as delay-seconds. Ignores HTTP-date form."""
    raw = response.headers.get("retry-after")
    if raw is None:
        return None
    try:
        value = float(str(raw).strip())
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def compute_retry_delay_seconds(
    attempt: int,
    response: httpx.Response | None = None,
) -> float:
    """Seconds to wait after a failed attempt before the next try.

    Prefer Retry-After when present (capped at 30s); otherwise use the fixed
    schedule: 5s / 10s / 20s for attempts 1 / 2 / 3.
    """
    if response is not None:
        retry_after = parse_retry_after_seconds(response)
        if retry_after is not None:
            return min(retry_after, _MAX_RETRY_AFTER_SECONDS)
    return _BACKOFF_SECONDS_BY_ATTEMPT.get(attempt, 20.0)


def create_anthropic_client(
    *,
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
) -> httpx.AsyncClient:
    """HTTP client for api.anthropic.com.

    ``trust_env`` honors HTTP(S)_PROXY / system proxy when enabled — required
    for local development behind VPN/proxy (confirmed: trust_env=False yields
    403 on networks where the direct route is blocked). Production keeps an
    explicit contract via ANTHROPIC_TRUST_ENV.
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        trust_env=config.ANTHROPIC_TRUST_ENV,
    )


@dataclass(frozen=True)
class SafeAnthropicError:
    """Provider error fields safe to log. Never carries prompts or keys."""

    status_code: int
    error_type: str | None
    error_message: str | None
    anthropic_request_id: str | None


def _sanitize_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = _CONTROL_CHARS.sub(" ", value).strip()
    if not text:
        return None
    return text[:_MAX_PROVIDER_MESSAGE_LENGTH]


def parse_anthropic_error(response: httpx.Response) -> SafeAnthropicError:
    """Extract a privacy-safe error summary from a non-200 Anthropic response.

    Only status, allowlisted error type, truncated sanitized message, and the
    provider request id are surfaced. Request body, headers, and any prompt
    content never leave this function.
    """
    request_id = _sanitize_text(response.headers.get("request-id"))

    error_type: str | None = None
    error_message: str | None = None
    try:
        payload = response.json()
    except ValueError:
        payload = None

    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            raw_type = error.get("type")
            if isinstance(raw_type, str) and raw_type in _KNOWN_ERROR_TYPES:
                error_type = raw_type
            elif isinstance(raw_type, str):
                error_type = _sanitize_text(raw_type)
            error_message = _sanitize_text(error.get("message"))

    if error_type is None:
        error_type = "unknown"
    if error_message is None:
        # Non-JSON body: keep a short sanitized excerpt for diagnostics.
        error_message = _sanitize_text(response.text) or "no_body"

    return SafeAnthropicError(
        status_code=response.status_code,
        error_type=error_type,
        error_message=error_message,
        anthropic_request_id=request_id,
    )
