"""Generation engine resolution (catalog_planner vs legacy_claude)."""

from __future__ import annotations

import logging
from enum import StrEnum

import config

logger = logging.getLogger(__name__)


class GenerationEngine(StrEnum):
    CATALOG_PLANNER = "catalog_planner"
    LEGACY_CLAUDE = "legacy_claude"


_VALID_ENGINES = {e.value for e in GenerationEngine}


def resolve_generation_engine(
    raw: str | None = None,
) -> GenerationEngine:
    """Resolve MEAL_GENERATION_ENGINE; invalid values fall back to catalog_planner."""
    value = (raw if raw is not None else getattr(config, "MEAL_GENERATION_ENGINE", "")).strip().lower()
    if not value:
        return GenerationEngine.CATALOG_PLANNER
    if value not in _VALID_ENGINES:
        logger.warning(
            "invalid_meal_generation_engine value=%r falling_back=%s",
            value,
            GenerationEngine.CATALOG_PLANNER.value,
        )
        return GenerationEngine.CATALOG_PLANNER
    return GenerationEngine(value)


def require_legacy_claude_credentials() -> None:
    """Raise if legacy Claude engine is selected without an API key."""
    from menu_generation.errors import CatalogGenerationError

    if not config.is_claude_configured():
        raise CatalogGenerationError(
            "Legacy Claude generation requires ANTHROPIC_API_KEY",
            code=CatalogGenerationError.GENERATION_ENGINE_UNAVAILABLE,
            details={
                "engine": GenerationEngine.LEGACY_CLAUDE.value,
                "missing": "ANTHROPIC_API_KEY",
            },
        )
    if not (config.CLAUDE_MODEL or "").strip():
        raise CatalogGenerationError(
            "Legacy Claude generation requires CLAUDE_MODEL",
            code=CatalogGenerationError.GENERATION_ENGINE_UNAVAILABLE,
            details={
                "engine": GenerationEngine.LEGACY_CLAUDE.value,
                "missing": "CLAUDE_MODEL",
            },
        )
