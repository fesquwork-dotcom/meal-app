"""Internal models for deterministic basket building."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

from menu_models import BasketCategory

WarningCode = Literal[
    "BASKET_INVALID_QUANTITY",
    "BASKET_INCOMPATIBLE_UNITS",
    "BASKET_PRICE_UNAVAILABLE",
    "BASKET_PRICE_ESTIMATED",
    "BASKET_NON_AGGREGATABLE",
    "BASKET_AMBIGUOUS_RECIPE",
    "BASKET_RECIPE_NOT_FOUND",
]


@dataclass(frozen=True)
class NormalizedIngredient:
    canonical_name: str
    display_name: str
    quantity: Decimal | None
    unit: str | None
    aggregatable: bool
    source_recipe_names: tuple[str, ...] = ()
    source_meal_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class BasketBuildWarning:
    code: WarningCode
    message: str
    path: str | None = None


@dataclass(frozen=True)
class CrossUnitMergeTrace:
    """Internal trace of the final canonical_name merge (not part of wire format)."""

    canonical_name: str
    source_units: tuple[str, ...]
    source_quantities: tuple[str, ...]
    preferred_unit: str | None
    grams_per_piece: str | None
    confidence: str | None
    result_quantity: str | None
    source_count: int
    applied: bool
    reason: str | None = None
    fallback_display: str | None = None


@dataclass
class BasketBuildResult:
    basket: list[BasketCategory]
    total_cost: Decimal | None
    warnings: list[BasketBuildWarning] = field(default_factory=list)
    unresolved_prices: list[str] = field(default_factory=list)
    merged_duplicate_count: int = 0
    raw_ingredient_count: int = 0
    basket_line_count: int = 0
    cross_unit_merges: list[CrossUnitMergeTrace] = field(default_factory=list)

    @property
    def has_fatal_pricing_gap(self) -> bool:
        return bool(self.unresolved_prices)
