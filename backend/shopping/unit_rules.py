"""Canonical unit rules: preferred units and pcs↔grams conversion catalog.

Sprint 10.5.2. Central registry — basket_builder must not hard-code
per-product conditions. Average piece weights are conservative retail
estimates for medium-size produce; every conversion using them is marked
approximate and displayed with the ≈ symbol.

Deliberately excluded (weight spread too large for a useful average):
cabbage, pumpkin, watermelon, melon, meat cuts, whole fish, bread,
cheese, packaged goods.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

CONFIDENCE_LEVELS = ("exact", "high", "approximate", "unknown")


@dataclass(frozen=True)
class CanonicalUnitRule:
    canonical_name: str
    preferred_unit: str
    grams_per_piece: Decimal | None
    confidence: str  # exact | high | approximate | unknown
    aliases: tuple[str, ...] = ()
    enabled: bool = True

    @property
    def allows_piece_conversion(self) -> bool:
        return (
            self.enabled
            and self.grams_per_piece is not None
            and self.grams_per_piece > 0
            and self.confidence in ("exact", "high", "approximate")
        )


# Average piece weights (grams). Sources: typical RU retail medium size.
CANONICAL_UNIT_RULES: tuple[CanonicalUnitRule, ...] = (
    CanonicalUnitRule(
        canonical_name="картофель",
        preferred_unit="g",
        grams_per_piece=Decimal("150"),  # средний клубень 120–180 г
        confidence="approximate",
        aliases=("картошка",),
    ),
    CanonicalUnitRule(
        canonical_name="помидор",
        preferred_unit="g",
        grams_per_piece=Decimal("110"),  # средний томат 90–130 г
        confidence="approximate",
        aliases=("томат", "помидоры", "томаты"),
    ),
    CanonicalUnitRule(
        canonical_name="огурец",
        preferred_unit="g",
        grams_per_piece=Decimal("100"),  # средний огурец 80–120 г
        confidence="approximate",
        aliases=("огурцы",),
    ),
    CanonicalUnitRule(
        canonical_name="морковь",
        preferred_unit="g",
        grams_per_piece=Decimal("100"),  # средняя морковь 80–120 г
        confidence="approximate",
        aliases=("морковка",),
    ),
    CanonicalUnitRule(
        canonical_name="лук репчатый",
        preferred_unit="g",
        grams_per_piece=Decimal("110"),  # средняя луковица 90–130 г
        confidence="approximate",
        aliases=("лук",),
    ),
    CanonicalUnitRule(
        canonical_name="яблоко",
        preferred_unit="g",
        grams_per_piece=Decimal("180"),  # среднее яблоко 150–200 г
        confidence="approximate",
        aliases=("яблоки",),
    ),
    CanonicalUnitRule(
        canonical_name="банан",
        preferred_unit="g",
        grams_per_piece=Decimal("120"),  # средний банан без кожуры ~120 г
        confidence="approximate",
        aliases=("бананы",),
    ),
    CanonicalUnitRule(
        canonical_name="лимон",
        preferred_unit="g",
        grams_per_piece=Decimal("120"),  # средний лимон 100–140 г
        confidence="approximate",
        aliases=("лимоны",),
    ),
    CanonicalUnitRule(
        canonical_name="авокадо",
        preferred_unit="g",
        grams_per_piece=Decimal("150"),  # среднее авокадо 130–170 г
        confidence="approximate",
    ),
    CanonicalUnitRule(
        canonical_name="болгарский перец",
        preferred_unit="g",
        grams_per_piece=Decimal("160"),  # средний перец 140–180 г
        confidence="approximate",
        aliases=("перец болгарский", "перец сладкий"),
    ),
)

_RULE_INDEX: dict[str, CanonicalUnitRule] = {}
for _rule in CANONICAL_UNIT_RULES:
    _RULE_INDEX[_rule.canonical_name] = _rule
    for _alias in _rule.aliases:
        _RULE_INDEX.setdefault(_alias, _rule)


def get_unit_rule(canonical_name: str) -> CanonicalUnitRule | None:
    return _RULE_INDEX.get(canonical_name)
