"""Production / development gates for Sprint 9.5 QA tools."""

from __future__ import annotations

import config


class DevToolsDisabledError(RuntimeError):
    """Raised when a development-only endpoint is called outside dev mode."""


def is_dev_tools_enabled() -> bool:
    """Dev reset/fixtures are available only with explicit local-dev auth.

    Production ENVIRONMENT with ALLOW_DEV_AUTH is rejected at startup; this
    helper is a second line of defense for the endpoints themselves.
    """
    if config.ENVIRONMENT == "production":
        return False
    return bool(config.ALLOW_DEV_AUTH)


def assert_dev_tools_enabled() -> None:
    if not is_dev_tools_enabled():
        raise DevToolsDisabledError("Development QA tools are disabled")
