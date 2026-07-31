"""Persistence helpers for immutable DecisionContext JSON."""

from __future__ import annotations

import logging

from decision.context import DecisionContext

logger = logging.getLogger(__name__)


class DecisionRepository:
    """Serializes/deserializes DecisionContext for weekly_strategies storage."""

    @staticmethod
    def dump(decision: DecisionContext | None) -> str | None:
        if decision is None:
            return None
        return decision.to_json()

    @staticmethod
    def load(raw: str | None) -> DecisionContext | None:
        if not raw:
            return None
        decision = DecisionContext.from_json(raw)
        if decision is None:
            logger.warning("decision_context_load_failed")
        return decision
