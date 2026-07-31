"""Unit and quantity parsing for basket aggregation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction

CANONICAL_UNITS = frozenset(
    {"g", "kg", "ml", "l", "pcs", "tbsp", "tsp", "package", "to_taste", "unknown"}
)

UNIT_ALIASES: dict[str, str] = {
    "г": "g",
    "гр": "g",
    "грамм": "g",
    "грамма": "g",
    "граммы": "g",
    "кг": "kg",
    "килограмм": "kg",
    "килограмма": "kg",
    "мл": "ml",
    "л": "l",
    "литр": "l",
    "литра": "l",
    "шт": "pcs",
    "штука": "pcs",
    "штуки": "pcs",
    "штук": "pcs",
    "ст.л": "tbsp",
    "ст. л": "tbsp",
    "столовая ложка": "tbsp",
    "ч.л": "tsp",
    "ч. л": "tsp",
    "чайная ложка": "tsp",
    "уп": "package",
    "упаковка": "package",
    "упаковки": "package",
    "по вкусу": "to_taste",
    "щепотка": "to_taste",
    "немного": "to_taste",
    "для подачи": "to_taste",
}

NON_AGGREGATABLE_UNITS = frozenset({"to_taste", "unknown"})

_AMOUNT_PATTERN = re.compile(
    r"^\s*(?P<qty>(?:\d+\s*/\s*\d+|\d+[\d,.]*))\s*(?P<unit>.+)?\s*$",
    re.IGNORECASE,
)
_TO_TASTE_PATTERN = re.compile(
    r"^(по вкусу|щепотка|немного|для подачи)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ParsedAmount:
    quantity: Decimal | None
    unit: str
    aggregatable: bool
    raw: str


def _parse_quantity_token(token: str) -> Decimal | None:
    cleaned = token.strip().replace(",", ".")
    if "/" in cleaned:
        parts = cleaned.split("/")
        if len(parts) == 2:
            try:
                return Decimal(str(float(Fraction(parts[0].strip()) / Fraction(parts[1].strip()))))
            except (ValueError, ZeroDivisionError, InvalidOperation):
                return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def normalize_unit(raw_unit: str | None) -> str:
    if raw_unit is None:
        return "unknown"
    unit = raw_unit.strip().lower().replace("ё", "е")
    unit = re.sub(r"\s+", " ", unit)
    if unit in UNIT_ALIASES:
        return UNIT_ALIASES[unit]
    if unit in CANONICAL_UNITS:
        return unit
    return "unknown"


def parse_amount(amount: str) -> ParsedAmount:
    raw = amount.strip()
    if not raw:
        return ParsedAmount(quantity=None, unit="unknown", aggregatable=False, raw=raw)

    if _TO_TASTE_PATTERN.match(raw):
        return ParsedAmount(quantity=None, unit="to_taste", aggregatable=False, raw=raw)

    match = _AMOUNT_PATTERN.match(raw)
    if not match:
        return ParsedAmount(quantity=None, unit="unknown", aggregatable=False, raw=raw)

    qty = _parse_quantity_token(match.group("qty"))
    unit_raw = match.group("unit")
    unit = normalize_unit(unit_raw.strip() if unit_raw else None)
    aggregatable = qty is not None and unit not in NON_AGGREGATABLE_UNITS
    return ParsedAmount(quantity=qty, unit=unit, aggregatable=aggregatable, raw=raw)


def units_compatible(left: str, right: str) -> bool:
    return left == right and left not in NON_AGGREGATABLE_UNITS and left != "unknown"


def convert_to_base(quantity: Decimal, unit: str) -> tuple[Decimal, str] | None:
    if unit == "kg":
        return quantity * Decimal("1000"), "g"
    if unit == "l":
        return quantity * Decimal("1000"), "ml"
    if unit in {"g", "ml", "pcs", "tbsp", "tsp", "package"}:
        return quantity, unit
    return None


def merge_quantities(
    left_qty: Decimal,
    left_unit: str,
    right_qty: Decimal,
    right_unit: str,
) -> tuple[Decimal, str] | None:
    left_base = convert_to_base(left_qty, left_unit)
    right_base = convert_to_base(right_qty, right_unit)
    if left_base is None or right_base is None:
        return None
    if left_base[1] != right_base[1]:
        return None
    return left_base[0] + right_base[0], left_base[1]


def format_decimal_plain(quantity: Decimal) -> str:
    """Fixed-point text without exponent form (Decimal.normalize() yields 1.2E+3 for 1200)."""
    text = format(quantity, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def format_weight(quantity: Decimal | None, unit: str, *, raw_fallback: str) -> str:
    if quantity is None or unit in NON_AGGREGATABLE_UNITS:
        return raw_fallback

    display_units = {
        "g": "г",
        "kg": "кг",
        "ml": "мл",
        "l": "л",
        "pcs": "шт",
        "tbsp": "ст.л",
        "tsp": "ч.л",
        "package": "уп",
    }
    label = display_units.get(unit, unit)
    return f"{format_decimal_plain(quantity)} {label}"


def format_quantity_human(quantity: Decimal, unit: str, *, approximate: bool = False) -> str:
    """Display formatting per Sprint 10.5.2: g≥1000 → кг, ml≥1000 → л, ≈ for approximations."""
    display_unit = unit
    value = quantity
    if unit == "g" and quantity >= 1000:
        value = (quantity / Decimal("1000")).quantize(Decimal("0.01"))
        display_unit = "kg"
    elif unit == "ml" and quantity >= 1000:
        value = (quantity / Decimal("1000")).quantize(Decimal("0.01"))
        display_unit = "l"

    labels = {
        "g": "г",
        "kg": "кг",
        "ml": "мл",
        "l": "л",
        "pcs": "шт",
        "tbsp": "ст.л",
        "tsp": "ч.л",
        "package": "уп",
    }
    label = labels.get(display_unit, display_unit)
    prefix = "≈" if approximate else ""
    return f"{prefix}{format_decimal_plain(value)} {label}"


class CanonicalUnitPolicy:
    """Preferred unit and pcs↔weight conversion policy per canonical product.

    The default policy resolves rules from the central catalog in
    shopping.unit_rules. resolve_unit stays a no-op for the primary
    aggregation (canonical_name + unit); cross-unit conversion happens
    only in the final merge stage via rule_for.
    """

    def resolve_unit(self, canonical_name: str, unit: str) -> str:
        return unit

    def rule_for(self, canonical_name: str):
        from shopping.unit_rules import get_unit_rule

        return get_unit_rule(canonical_name)


DEFAULT_UNIT_POLICY = CanonicalUnitPolicy()
