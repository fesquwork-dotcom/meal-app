"""Single entry point for menu generation (catalog planner or legacy Claude)."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Any, Optional

from menu_generation.catalog_service import CatalogMenuGenerationService
from menu_generation.engine import (
    GenerationEngine,
    require_legacy_claude_credentials,
    resolve_generation_engine,
)
from recipes.quality.enums import QualityStatus
from strategy.models import WeeklyStrategy

logger = logging.getLogger(__name__)


class MenuGenerationOrchestrator:
    """Routes menu generation to catalog_planner or legacy_claude."""

    def __init__(
        self,
        *,
        db_path: Path | str | None = None,
        catalog_service: CatalogMenuGenerationService | None = None,
    ) -> None:
        self._db_path = db_path
        self._catalog_service = catalog_service

    def _get_catalog_service(self) -> CatalogMenuGenerationService:
        if self._catalog_service is None:
            self._catalog_service = CatalogMenuGenerationService(db_path=self._db_path)
        return self._catalog_service

    async def generate_menu(
        self,
        budget: float,
        days: int,
        meal_types: list[str],
        meals_per_day: int,
        persons: int,
        proteins: list,
        goal: str,
        cooktime: str,
        allergies: str,
        store: str = "any",
        user_id: Optional[int] = None,
        strategy: WeeklyStrategy | None = None,
        plan_start_date: date | None = None,
        progress_callback: Any = None,
        minimum_quality_status: QualityStatus | None = None,
        strategy_id: str | None = None,
    ) -> dict[str, object]:
        engine = resolve_generation_engine()
        logger.info(
            "menu_generation_engine_selected engine=%s user_id=%s",
            engine.value,
            user_id,
        )

        if engine == GenerationEngine.CATALOG_PLANNER:
            if strategy is None:
                from menu_generation.errors import CatalogGenerationError

                raise CatalogGenerationError(
                    "Catalog planner requires a WeeklyStrategy",
                    code=CatalogGenerationError.GENERATION_ENGINE_UNAVAILABLE,
                    details={"engine": engine.value},
                )
            return await self._get_catalog_service().generate(
                strategy=strategy,
                persons=persons,
                proteins=proteins,
                cooktime=cooktime,
                allergies=allergies,
                store=store,
                user_id=user_id,
                plan_start_date=plan_start_date,
                progress_callback=progress_callback,
                minimum_quality_status=minimum_quality_status,
                strategy_id=strategy_id,
            )

        require_legacy_claude_credentials()
        # Lazy import so catalog path never loads Anthropic client.
        from claude_service import generate_menu as claude_generate_menu

        return await claude_generate_menu(
            budget=budget,
            days=days,
            meal_types=meal_types,
            meals_per_day=meals_per_day,
            persons=persons,
            proteins=proteins,
            goal=goal,
            cooktime=cooktime,
            allergies=allergies,
            store=store,
            user_id=user_id,
            strategy=strategy,
            plan_start_date=plan_start_date,
            progress_callback=progress_callback,
        )


_default_orchestrator = MenuGenerationOrchestrator()


async def generate_menu(**kwargs: Any) -> dict[str, object]:
    """Module-level entry used by main.py and generation_jobs/execute.py."""
    return await _default_orchestrator.generate_menu(**kwargs)
