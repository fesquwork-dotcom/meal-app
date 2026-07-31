"""Immutable DecisionContext — the full resolved decision set for one strategy build."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field

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

logger = logging.getLogger(__name__)


def _reasons_to_dicts(reasons: tuple[DecisionReason, ...]) -> list[dict[str, object]]:
    return [
        {
            "code": reason.code,
            "source": reason.source,
            "priority": reason.priority,
            "description": reason.description,
        }
        for reason in reasons
    ]


def _reasons_from_dicts(raw: object) -> tuple[DecisionReason, ...]:
    if not isinstance(raw, list):
        return ()
    reasons: list[DecisionReason] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        source = item.get("source")
        priority = item.get("priority")
        if not isinstance(code, str) or not isinstance(source, str):
            continue
        if not isinstance(priority, int) or isinstance(priority, bool):
            continue
        description = item.get("description")
        reasons.append(
            DecisionReason(
                code=code,
                source=source,  # type: ignore[arg-type]
                priority=priority,
                description=description if isinstance(description, str) else "",
            )
        )
    return tuple(reasons)


@dataclass(frozen=True)
class DecisionContext:
    """Pre-computed decisions. StrategyBuilder maps this to WeeklyStrategy only."""

    goal: str
    days: int
    meal_types: list[str]
    meals_per_day: int
    generated_at: str
    budget: BudgetDecision
    cooking: CookingDecision
    protein: ProteinDecision
    shopping: ShoppingDecision
    behavior: BehaviorDecision
    memory: MemoryDecision
    excluded_products: list[str] = field(default_factory=list)
    decision_version: int = DECISION_VERSION
    strategy_version: int = STRATEGY_VERSION_WITH_DECISIONS
    reason_codes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "decision_version": self.decision_version,
            "strategy_version": self.strategy_version,
            "goal": self.goal,
            "days": self.days,
            "meal_types": list(self.meal_types),
            "meals_per_day": self.meals_per_day,
            "generated_at": self.generated_at,
            "excluded_products": list(self.excluded_products),
            "budget": {
                "daily_budget": self.budget.daily_budget,
                "weekly_budget": self.budget.weekly_budget,
                "priority": self.budget.priority,
                "reasons": _reasons_to_dicts(self.budget.reasons),
            },
            "cooking": {
                "time_limit": self.cooking.time_limit,
                "prefer_faster": self.cooking.prefer_faster,
                "cook_days": list(self.cooking.cook_days),
                "batch_allowed": self.cooking.batch_allowed,
                "leftovers_enabled": self.cooking.leftovers_enabled,
                "repeat_breakfasts": self.cooking.repeat_breakfasts,
                "repeat_lunches": self.cooking.repeat_lunches,
                "repeat_dinners": self.cooking.repeat_dinners,
                "preference_source": self.cooking.preference_source,
                "profile_prefer_faster": self.cooking.profile_prefer_faster,
                "cooktime_band": self.cooking.cooktime_band,
                "reasons": _reasons_to_dicts(self.cooking.reasons),
            },
            "protein": {
                "allowed": list(self.protein.allowed),
                "preferred": list(self.protein.preferred),
                "blocked": list(self.protein.blocked),
                "reasons": _reasons_to_dicts(self.protein.reasons),
            },
            "shopping": {
                "shopping_days": list(self.shopping.shopping_days),
                "fresh_products_days": list(self.shopping.fresh_products_days),
                "reasons": _reasons_to_dicts(self.shopping.reasons),
            },
            "behavior": {
                "prefer_familiar": self.behavior.prefer_familiar,
                "availability_avoid_products": list(
                    self.behavior.availability_avoid_products
                ),
                "confirmed_behavior_count": self.behavior.confirmed_behavior_count,
                "familiar_source": self.behavior.familiar_source,
                "familiar_profile_value": self.behavior.familiar_profile_value,
                "reasons": _reasons_to_dicts(self.behavior.reasons),
            },
            "memory": {
                "confirmed_preferences": list(self.memory.confirmed_preferences),
                "temporary_avoids": list(self.memory.temporary_avoids),
                "active_signal_count": self.memory.active_signal_count,
                "prefer_faster_from_memory": self.memory.prefer_faster_from_memory,
                "reasons": _reasons_to_dicts(self.memory.reasons),
            },
            "reason_codes": list(self.reason_codes),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> "DecisionContext | None":
        try:
            budget_raw = payload.get("budget")
            cooking_raw = payload.get("cooking")
            protein_raw = payload.get("protein")
            shopping_raw = payload.get("shopping")
            behavior_raw = payload.get("behavior")
            memory_raw = payload.get("memory")
            if not all(
                isinstance(item, dict)
                for item in (
                    budget_raw,
                    cooking_raw,
                    protein_raw,
                    shopping_raw,
                    behavior_raw,
                    memory_raw,
                )
            ):
                return None

            goal = payload.get("goal")
            days = payload.get("days")
            meal_types = payload.get("meal_types")
            meals_per_day = payload.get("meals_per_day")
            generated_at = payload.get("generated_at")
            if not isinstance(goal, str) or not isinstance(generated_at, str):
                return None
            if not isinstance(days, int) or isinstance(days, bool):
                return None
            if not isinstance(meals_per_day, int) or isinstance(meals_per_day, bool):
                return None
            if not isinstance(meal_types, list):
                return None

            excluded = payload.get("excluded_products", [])
            if not isinstance(excluded, list):
                excluded = []

            reason_codes_raw = payload.get("reason_codes", [])
            reason_codes = (
                tuple(item for item in reason_codes_raw if isinstance(item, str))
                if isinstance(reason_codes_raw, list)
                else ()
            )

            decision_version = payload.get("decision_version", DECISION_VERSION)
            strategy_version = payload.get(
                "strategy_version", STRATEGY_VERSION_WITH_DECISIONS
            )

            return cls(
                decision_version=int(decision_version)
                if isinstance(decision_version, int)
                else DECISION_VERSION,
                strategy_version=int(strategy_version)
                if isinstance(strategy_version, int)
                else STRATEGY_VERSION_WITH_DECISIONS,
                goal=goal,
                days=days,
                meal_types=[item for item in meal_types if isinstance(item, str)],
                meals_per_day=meals_per_day,
                generated_at=generated_at,
                excluded_products=[item for item in excluded if isinstance(item, str)],
                budget=BudgetDecision(
                    daily_budget=float(budget_raw["daily_budget"]),  # type: ignore[index]
                    weekly_budget=float(budget_raw["weekly_budget"]),  # type: ignore[index]
                    priority=str(budget_raw.get("priority") or "standard"),  # type: ignore[union-attr]
                    reasons=_reasons_from_dicts(budget_raw.get("reasons")),  # type: ignore[union-attr]
                ),
                cooking=CookingDecision(
                    time_limit=int(cooking_raw["time_limit"]),  # type: ignore[index]
                    prefer_faster=bool(cooking_raw.get("prefer_faster")),  # type: ignore[union-attr]
                    cook_days=[
                        int(day)
                        for day in cooking_raw.get("cook_days", [])  # type: ignore[union-attr]
                        if isinstance(day, int) and not isinstance(day, bool)
                    ],
                    batch_allowed=bool(cooking_raw.get("batch_allowed")),  # type: ignore[union-attr]
                    leftovers_enabled=bool(cooking_raw.get("leftovers_enabled")),  # type: ignore[union-attr]
                    repeat_breakfasts=bool(cooking_raw.get("repeat_breakfasts")),  # type: ignore[union-attr]
                    repeat_lunches=bool(cooking_raw.get("repeat_lunches")),  # type: ignore[union-attr]
                    repeat_dinners=bool(cooking_raw.get("repeat_dinners")),  # type: ignore[union-attr]
                    preference_source=str(  # type: ignore[arg-type]
                        cooking_raw.get("preference_source") or "default"
                    ),
                    profile_prefer_faster=cooking_raw.get("profile_prefer_faster")  # type: ignore[union-attr]
                    if isinstance(cooking_raw.get("profile_prefer_faster"), bool)  # type: ignore[union-attr]
                    else None,
                    cooktime_band=str(cooking_raw.get("cooktime_band") or "medium"),  # type: ignore[union-attr]
                    reasons=_reasons_from_dicts(cooking_raw.get("reasons")),  # type: ignore[union-attr]
                ),
                protein=ProteinDecision(
                    allowed=[
                        item
                        for item in protein_raw.get("allowed", [])  # type: ignore[union-attr]
                        if isinstance(item, str)
                    ],
                    preferred=[
                        item
                        for item in protein_raw.get("preferred", [])  # type: ignore[union-attr]
                        if isinstance(item, str)
                    ],
                    blocked=[
                        item
                        for item in protein_raw.get("blocked", [])  # type: ignore[union-attr]
                        if isinstance(item, str)
                    ],
                    reasons=_reasons_from_dicts(protein_raw.get("reasons")),  # type: ignore[union-attr]
                ),
                shopping=ShoppingDecision(
                    shopping_days=[
                        int(day)
                        for day in shopping_raw.get("shopping_days", [])  # type: ignore[union-attr]
                        if isinstance(day, int) and not isinstance(day, bool)
                    ],
                    fresh_products_days=[
                        int(day)
                        for day in shopping_raw.get("fresh_products_days", [])  # type: ignore[union-attr]
                        if isinstance(day, int) and not isinstance(day, bool)
                    ],
                    reasons=_reasons_from_dicts(shopping_raw.get("reasons")),  # type: ignore[union-attr]
                ),
                behavior=BehaviorDecision(
                    prefer_familiar=bool(behavior_raw.get("prefer_familiar")),  # type: ignore[union-attr]
                    availability_avoid_products=[
                        item
                        for item in behavior_raw.get("availability_avoid_products", [])  # type: ignore[union-attr]
                        if isinstance(item, str)
                    ],
                    confirmed_behavior_count=int(
                        behavior_raw.get("confirmed_behavior_count") or 0  # type: ignore[union-attr]
                    ),
                    familiar_source=str(  # type: ignore[arg-type]
                        behavior_raw.get("familiar_source") or "default"
                    ),
                    familiar_profile_value=behavior_raw.get("familiar_profile_value")  # type: ignore[union-attr]
                    if isinstance(behavior_raw.get("familiar_profile_value"), bool)  # type: ignore[union-attr]
                    else None,
                    reasons=_reasons_from_dicts(behavior_raw.get("reasons")),  # type: ignore[union-attr]
                ),
                memory=MemoryDecision(
                    confirmed_preferences=[
                        item
                        for item in memory_raw.get("confirmed_preferences", [])  # type: ignore[union-attr]
                        if isinstance(item, str)
                    ],
                    temporary_avoids=[
                        item
                        for item in memory_raw.get("temporary_avoids", [])  # type: ignore[union-attr]
                        if isinstance(item, str)
                    ],
                    active_signal_count=int(memory_raw.get("active_signal_count") or 0),  # type: ignore[union-attr]
                    prefer_faster_from_memory=bool(
                        memory_raw.get("prefer_faster_from_memory")  # type: ignore[union-attr]
                    ),
                    reasons=_reasons_from_dicts(memory_raw.get("reasons")),  # type: ignore[union-attr]
                ),
                reason_codes=reason_codes,
            )
        except (KeyError, TypeError, ValueError) as exc:
            logger.warning("decision_context_from_dict_failed error=%s", exc)
            return None

    @classmethod
    def from_json(cls, raw: str | None) -> "DecisionContext | None":
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("decision_context_json_malformed")
            return None
        if not isinstance(parsed, dict):
            return None
        return cls.from_dict(parsed)
