import os
from pathlib import Path

from dotenv import load_dotenv
import logging

load_dotenv()
logger = logging.getLogger(__name__)

ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()


def _resolve_anthropic_api_key() -> str:
    """Primary env name: ANTHROPIC_API_KEY. CLAUDE_API_KEY is a deprecated fallback."""
    primary = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if primary:
        return primary

    legacy = os.getenv("CLAUDE_API_KEY", "").strip()
    if legacy:
        logger.warning("CLAUDE_API_KEY is deprecated; use ANTHROPIC_API_KEY instead")
        return legacy

    return ""


ANTHROPIC_API_KEY = _resolve_anthropic_api_key()
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-3-5-sonnet-20241022")
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "16000"))

# Strict JSON generation does not need extended thinking. On models where
# thinking is on by default, reasoning tokens count against max_tokens and can
# consume the entire output budget before the final text block (observed:
# stop_reason=max_tokens, output_tokens=16000, raw_chars=0).
CLAUDE_DISABLE_THINKING = os.getenv("CLAUDE_DISABLE_THINKING", "true").strip().lower() in (
    "1",
    "true",
    "yes",
)

# Soft budget-utilization upgrade after a successful underutilized generation.
# Disabled in ENVIRONMENT=qa; override with BUDGET_OPTIMIZER_ENABLED=0/1.
_BUDGET_OPTIMIZER_DEFAULT = "0" if ENVIRONMENT == "qa" else "1"
BUDGET_OPTIMIZER_ENABLED = os.getenv(
    "BUDGET_OPTIMIZER_ENABLED", _BUDGET_OPTIMIZER_DEFAULT
).strip().lower() in ("1", "true", "yes")

# Anthropic HTTP transport (network hotfix): when true, httpx honors
# HTTP_PROXY / HTTPS_PROXY / system proxy variables. Local development behind
# VPN/proxy needs this (direct route can return 403). Production defaults to
# an explicit, environment-independent transport.
def parse_anthropic_trust_env(raw: str | None, environment: str) -> bool:
    """Development default = true, production default = false."""
    if raw is None:
        raw = "true" if environment == "development" else "false"
    return raw.strip().lower() in ("1", "true", "yes")


ANTHROPIC_TRUST_ENV = parse_anthropic_trust_env(
    os.getenv("ANTHROPIC_TRUST_ENV"), ENVIRONMENT
)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
ALLOW_DEV_AUTH = os.getenv("ALLOW_DEV_AUTH", "false").lower() in ("1", "true", "yes")
DEV_TELEGRAM_USER_ID = int(os.getenv("DEV_TELEGRAM_USER_ID", "1"))
TELEGRAM_INIT_DATA_MAX_AGE_SECONDS = int(os.getenv("TELEGRAM_INIT_DATA_MAX_AGE_SECONDS", "3600"))
TELEGRAM_AUTH_CLOCK_SKEW_SECONDS = int(os.getenv("TELEGRAM_AUTH_CLOCK_SKEW_SECONDS", "60"))

DATABASE_PATH = os.getenv("DATABASE_PATH", "./app.db")

# Adaptive Intelligence (Sprint 9.1): when false, Learned Preferences never
# influence planning/Decision. The read/write API stays available regardless.
ADAPTIVE_PREFERENCES = os.getenv("ADAPTIVE_PREFERENCES", "false").lower() in (
    "1",
    "true",
    "yes",
)

# Signed strategy preview tokens (Sprint 5.16)
STRATEGY_PREVIEW_SECRET = os.getenv("STRATEGY_PREVIEW_SECRET", "").strip()
PREVIEW_TOKEN_TTL_SECONDS = int(os.getenv("PREVIEW_TOKEN_TTL_SECONDS", "900"))
_DEV_PREVIEW_SECRET = "dev-preview-secret-not-for-production"


def get_strategy_preview_secret() -> str:
    """Returns preview signing secret; production requires explicit configuration."""
    if STRATEGY_PREVIEW_SECRET:
        return STRATEGY_PREVIEW_SECRET
    if ALLOW_DEV_AUTH:
        return _DEV_PREVIEW_SECRET
    raise RuntimeError("STRATEGY_PREVIEW_SECRET is required")

_DEFAULT_ALLOWED_ORIGINS = "http://localhost:5173,http://127.0.0.1:5173"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", _DEFAULT_ALLOWED_ORIGINS).split(",")
    if origin.strip()
]

IS_PRODUCTION_MODE = not ALLOW_DEV_AUTH

# App label for health/diagnostics (not a secret; safe to expose).
APP_VERSION = os.getenv("APP_VERSION", "9.5.0").strip() or "9.5.0"


def is_claude_configured() -> bool:
    """True when Claude API key is available (same source as claude_service)."""
    return bool(ANTHROPIC_API_KEY)


def is_dev_tools_enabled() -> bool:
    """True when controlled reset / QA fixtures may run."""
    if ENVIRONMENT == "production":
        return False
    return ALLOW_DEV_AUTH


if not ANTHROPIC_API_KEY and not IS_PRODUCTION_MODE:
    logger.warning("⚠️ ANTHROPIC_API_KEY не найден в .env!")

if ALLOW_DEV_AUTH:
    logger.warning(
        "⚠️ ALLOW_DEV_AUTH=true: backend accepts unauthenticated requests as DEV_TELEGRAM_USER_ID=%s",
        DEV_TELEGRAM_USER_ID,
    )

if not TELEGRAM_BOT_TOKEN and IS_PRODUCTION_MODE:
    logger.warning("⚠️ TELEGRAM_BOT_TOKEN не задан — production auth будет недоступен")
