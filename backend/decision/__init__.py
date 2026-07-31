"""Decision Engine — sole authority for resolving strategic decisions."""

from decision.context import DecisionContext
from decision.models import (
    BehaviorDecision,
    BudgetDecision,
    CookingDecision,
    DecisionReason,
    MemoryDecision,
    ProteinDecision,
    ShoppingDecision,
)
from decision.versions import DECISION_VERSION, STRATEGY_VERSION_WITH_DECISIONS

# Engine is imported lazily by callers that need evaluate(); keeping it out of
# eager package imports avoids strategy↔decision circular imports.

__all__ = [
    "BehaviorDecision",
    "BudgetDecision",
    "CookingDecision",
    "DECISION_VERSION",
    "DecisionContext",
    "DecisionReason",
    "MemoryDecision",
    "ProteinDecision",
    "STRATEGY_VERSION_WITH_DECISIONS",
    "ShoppingDecision",
]


def __getattr__(name: str):
    if name in {"DecisionEngine", "DecisionEvaluationResult"}:
        from decision.engine import DecisionEngine, DecisionEvaluationResult

        return {
            "DecisionEngine": DecisionEngine,
            "DecisionEvaluationResult": DecisionEvaluationResult,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
