"""Sprint 9.5 — development-only QA tools (reset, fixtures, consistency).

Never importable into Decision Engine planning paths. Gated by ALLOW_DEV_AUTH
and ENVIRONMENT != production.
"""

from __future__ import annotations

from dev_tools.clock import QA_ANCHOR_DATE, qa_plan_date
from dev_tools.guards import (
    DevToolsDisabledError,
    assert_dev_tools_enabled,
    is_dev_tools_enabled,
)

__all__ = [
    "QA_ANCHOR_DATE",
    "DevToolsDisabledError",
    "assert_dev_tools_enabled",
    "is_dev_tools_enabled",
    "qa_plan_date",
]
