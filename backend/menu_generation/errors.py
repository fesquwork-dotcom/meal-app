"""Typed errors for catalog planner menu generation."""

from __future__ import annotations

from typing import Any


class CatalogGenerationError(Exception):
    """Raised when catalog-planner menu generation fails."""

    PLANNER_NO_PLAN = "PLANNER_NO_PLAN"
    PLANNER_PARTIAL_PLAN = "PLANNER_PARTIAL_PLAN"
    PLANNER_VALIDATION_FAILED = "PLANNER_VALIDATION_FAILED"
    CATALOG_RECIPE_NOT_FOUND = "CATALOG_RECIPE_NOT_FOUND"
    MENUPLAN_ADAPTER_FAILED = "MENUPLAN_ADAPTER_FAILED"
    MENUPLAN_VALIDATION_FAILED = "MENUPLAN_VALIDATION_FAILED"
    BASKET_BUILD_FAILED = "BASKET_BUILD_FAILED"
    GENERATION_ENGINE_UNAVAILABLE = "GENERATION_ENGINE_UNAVAILABLE"
    CATALOG_REPLACE_NOT_IMPLEMENTED = "CATALOG_REPLACE_NOT_IMPLEMENTED"

    def __init__(
        self,
        message: str,
        *,
        code: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
