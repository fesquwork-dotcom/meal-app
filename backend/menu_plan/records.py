"""Persistence records for durable menu plans."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class MenuPlanStatus(StrEnum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class MenuPlanChangeType(StrEnum):
    INITIAL = "initial"
    MEAL_REPLACEMENT = "meal_replacement"
    BASKET_REBUILD = "basket_rebuild"


@dataclass(frozen=True)
class MenuPlanRecord:
    """Row representation from the menu_plans table."""

    id: str
    user_id: int
    strategy_id: str
    status: str
    current_revision: int
    original_plan_json: str
    created_at: str
    updated_at: str
    superseded_at: str | None


@dataclass(frozen=True)
class MenuPlanRevisionRecord:
    """Row representation from the append-only menu_plan_revisions table."""

    menu_plan_id: str
    revision: int
    change_type: str
    plan_json: str
    changed_meal_ids_json: str | None
    created_at: str
