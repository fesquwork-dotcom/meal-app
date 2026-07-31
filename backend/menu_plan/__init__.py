"""Durable MenuPlan foundation (Sprint 7.2).

The backend is the authoritative store for generated menus: an immutable
original snapshot plus append-only validated revisions with optimistic
concurrency. Frontend localStorage remains an offline cache only.
"""

from menu_plan.exceptions import (
    MenuPlanConcurrencyError,
    MenuPlanNotFoundError,
    MenuPlanPersistenceError,
)
from menu_plan.records import (
    MenuPlanChangeType,
    MenuPlanRecord,
    MenuPlanRevisionRecord,
    MenuPlanStatus,
)
from menu_plan.repository import MenuPlanRepository
from menu_plan.service import MenuPlanService

__all__ = [
    "MenuPlanChangeType",
    "MenuPlanConcurrencyError",
    "MenuPlanNotFoundError",
    "MenuPlanPersistenceError",
    "MenuPlanRecord",
    "MenuPlanRepository",
    "MenuPlanRevisionRecord",
    "MenuPlanService",
    "MenuPlanStatus",
]
