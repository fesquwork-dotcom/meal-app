"""Immutable decision sub-models consumed by StrategyBuilder."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

DecisionSource = Literal[
    "profile",
    "memory",
    "behavior",
    "rule",
    "default",
    "runtime",
]


@dataclass(frozen=True)
class DecisionReason:
    code: str
    source: DecisionSource
    priority: int
    description: str = ""


@dataclass(frozen=True)
class BudgetDecision:
    daily_budget: float
    weekly_budget: float
    priority: str
    reasons: tuple[DecisionReason, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CookingDecision:
    time_limit: int
    prefer_faster: bool
    cook_days: list[int]
    batch_allowed: bool
    leftovers_enabled: bool
    repeat_breakfasts: bool
    repeat_lunches: bool
    repeat_dinners: bool
    preference_source: Literal["profile", "memory", "default"]
    profile_prefer_faster: bool | None = None
    cooktime_band: str = "medium"
    reasons: tuple[DecisionReason, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ProteinDecision:
    allowed: list[str]
    preferred: list[str]
    blocked: list[str] = field(default_factory=list)
    reasons: tuple[DecisionReason, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ShoppingDecision:
    shopping_days: list[int]
    fresh_products_days: list[int]
    reasons: tuple[DecisionReason, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BehaviorDecision:
    prefer_familiar: bool
    availability_avoid_products: list[str]
    confirmed_behavior_count: int
    familiar_source: Literal["profile", "default", "inferred"] = "default"
    familiar_profile_value: bool | None = None
    reasons: tuple[DecisionReason, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MemoryDecision:
    confirmed_preferences: list[str]
    temporary_avoids: list[str]
    active_signal_count: int
    prefer_faster_from_memory: bool = False
    reasons: tuple[DecisionReason, ...] = field(default_factory=tuple)
