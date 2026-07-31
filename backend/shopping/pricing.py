"""Price hints and estimation for rebuilt basket lines."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from menu_models import BasketCategory
from menu_validation import _is_pantry_staple
from shopping.normalization import canonical_ingredient_name
from shopping.units import merge_quantities, parse_amount

# Conservative fallback prices (₽) for common products when no hint exists.
FALLBACK_PRICES: dict[str, Decimal] = {
    "куриная грудка": Decimal("350"),
    "картофель": Decimal("80"),
    "морковь": Decimal("60"),
    "лук": Decimal("40"),
    "рис": Decimal("120"),
    "гречка": Decimal("110"),
    "молоко": Decimal("90"),
    "яйца": Decimal("120"),
    "творог": Decimal("150"),
    "помидор": Decimal("200"),
    "огурец": Decimal("120"),
    "овсянка": Decimal("90"),
}


@dataclass(frozen=True)
class PriceHint:
    price: Decimal
    amount_raw: str
    source: str  # "existing_basket" | "fallback"


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def extract_price_hints(basket: list[BasketCategory]) -> dict[str, PriceHint]:
    hints: dict[str, PriceHint] = {}
    for category in basket:
        for item in category.items:
            key = canonical_ingredient_name(item.name)
            if not key or key in hints:
                continue
            hints[key] = PriceHint(
                price=Decimal(str(item.price)),
                amount_raw=item.weight,
                source="existing_basket",
            )
    return hints


def estimate_line_price(
    *,
    canonical_name: str,
    display_name: str,
    weight: str,
    price_hints: dict[str, PriceHint],
) -> tuple[Decimal | None, str]:
    """Returns (price, source) where source is known|estimated|unknown."""
    product_key = canonical_ingredient_name(display_name)
    hint = price_hints.get(product_key) or price_hints.get(canonical_name)

    if hint is not None:
        if not weight or not hint.amount_raw:
            return _money(hint.price), "known"

        parsed_new = parse_amount(weight)
        parsed_old = parse_amount(hint.amount_raw)
        if (
            parsed_new.aggregatable
            and parsed_old.aggregatable
            and parsed_new.quantity is not None
            and parsed_old.quantity is not None
            and parsed_new.unit == parsed_old.unit
        ):
            merged = merge_quantities(
                parsed_new.quantity,
                parsed_new.unit,
                parsed_old.quantity,
                parsed_old.unit,
            )
            if merged and merged[0] > 0:
                ratio = parsed_new.quantity / parsed_old.quantity
                return _money(hint.price * ratio), "estimated"

        return _money(hint.price), "estimated"

    fallback_key = canonical_ingredient_name(display_name)
    if fallback_key in FALLBACK_PRICES:
        return _money(FALLBACK_PRICES[fallback_key]), "estimated"

    if _is_pantry_staple(display_name):
        return Decimal("0"), "known"

    return None, "unknown"
