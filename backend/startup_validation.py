"""Production startup configuration validation."""

from __future__ import annotations

import os
from pathlib import Path

import config


class StartupConfigurationError(RuntimeError):
    """Raised when mandatory production configuration is missing or unsafe."""


def _is_localhost_origin(origin: str) -> bool:
    lowered = origin.lower()
    return "localhost" in lowered or "127.0.0.1" in lowered


def _validate_database_path() -> None:
    db_path = Path(config.DATABASE_PATH).expanduser().resolve()
    parent = db_path.parent

    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StartupConfigurationError(
            f"DATABASE_PATH parent directory is not writable: {parent}"
        ) from exc

    if parent.exists() and not os.access(parent, os.W_OK):
        raise StartupConfigurationError(
            f"DATABASE_PATH parent directory is not writable: {parent}"
        )


def validate_startup_configuration() -> None:
    """Validates environment before serving traffic in production mode."""
    errors: list[str] = []

    if config.ENVIRONMENT == "production" and config.ALLOW_DEV_AUTH:
        errors.append(
            "ALLOW_DEV_AUTH cannot be enabled when ENVIRONMENT=production. "
            "Disable ALLOW_DEV_AUTH or use ENVIRONMENT=development for local QA."
        )

    if config.ENVIRONMENT == "production":
        for origin in config.ALLOWED_ORIGINS:
            if _is_localhost_origin(origin):
                errors.append(
                    "Localhost CORS origin is not allowed when ENVIRONMENT=production: "
                    f"{origin}"
                )

    if not config.ALLOW_DEV_AUTH:
        if not config.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required when ALLOW_DEV_AUTH=false")

        if not config.ALLOWED_ORIGINS:
            errors.append("ALLOWED_ORIGINS must not be empty")

        if "*" in config.ALLOWED_ORIGINS:
            errors.append("Wildcard CORS origin is not allowed with credentials")

        for origin in config.ALLOWED_ORIGINS:
            if origin == "*":
                errors.append("Wildcard CORS origin is not allowed with credentials")

        if not config.is_claude_configured():
            errors.append(
                "ANTHROPIC_API_KEY is missing. "
                "Menu generation is unavailable without it."
            )

        if not config.CLAUDE_MODEL:
            errors.append(
                "CLAUDE_MODEL is empty. Set CLAUDE_MODEL to a supported Anthropic "
                "model id (for example claude-sonnet-4-6)."
            )

        if not config.STRATEGY_PREVIEW_SECRET:
            errors.append("STRATEGY_PREVIEW_SECRET is required when ALLOW_DEV_AUTH=false")

    try:
        config.get_strategy_preview_secret()
    except RuntimeError as exc:
        if not config.ALLOW_DEV_AUTH:
            errors.append(str(exc))

    try:
        _validate_database_path()
    except StartupConfigurationError as exc:
        errors.append(str(exc))

    if errors:
        raise StartupConfigurationError("; ".join(errors))


def validate_cors_origins(origins: list[str]) -> None:
    """Rejects wildcard origins for credentialed CORS."""
    if "*" in origins:
        raise StartupConfigurationError("Wildcard CORS origin is not allowed with credentials")
