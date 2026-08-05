"""Catalog-planner menu generation (Sprint 10.11).

Default production engine. Legacy Claude remains behind MEAL_GENERATION_ENGINE=legacy_claude.
"""

from menu_generation.engine import GenerationEngine, resolve_generation_engine
from menu_generation.errors import CatalogGenerationError
from menu_generation.orchestrator import MenuGenerationOrchestrator, generate_menu

__all__ = [
    "CatalogGenerationError",
    "GenerationEngine",
    "MenuGenerationOrchestrator",
    "generate_menu",
    "resolve_generation_engine",
]
