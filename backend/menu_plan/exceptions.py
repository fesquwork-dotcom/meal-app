"""Domain exceptions for durable MenuPlan persistence (Sprint 7.2)."""

from __future__ import annotations


class MenuPlanNotFoundError(Exception):
    """Menu plan does not exist or belongs to another user."""


class MenuPlanConcurrencyError(Exception):
    """Expected revision no longer matches the stored current revision."""


class MenuPlanPersistenceError(Exception):
    """Storage failure while reading or writing menu plan state."""
