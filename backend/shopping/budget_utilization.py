"""Budget utilization: recipe cost vs shopping cost (Sprint 10.5.4).

Shopping cost = rebuilt basket total (what the user pays).
Recipe cost = estimated cost of exact recipe ingredient amounts after
canonical+unit merge, priced linearly from hints — without package ceil.
When shopping > recipe, the gap is explained as full-package purchasing.

Does not modify Basket Engine aggregation or CanonicalUnitPolicy.
"""

from __future__ import annotations

import logging
import math
from collections import OrderedDict
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from menu_models import MenuPlan
from menu_validation import _is_pantry_staple
from shopping.normalization import canonical_ingredient_name, display_ingredient_name
from shopping.pricing import estimate_line_price, extract_price_hints
from shopping.recipe_selection import get_active_ingredient_contributions
from shopping.units import format_weight, merge_quantities, parse_amount

logger = logging.getLogger(__name__)

TARGET_USAGE_MIN = Decimal("0.90")
TARGET_USAGE_MAX = Decimal("1.00")


@dataclass(frozen=True)
class BudgetUtilization:
    budget_limit: float
    recipe_cost: float
    shopping_cost: float
    budget_usage_percent: float
    pack_gap: float
    in_target_range: bool
    underutilized: bool

    def as_wire_fields(self) -> dict[str, float]:
        """Optional additive MenuPlan fields (backward compatible)."""
        return {
            "budget_limit": round(self.budget_limit, 2),
            "recipe_cost": round(self.recipe_cost, 2),
            "shopping_cost": round(self.shopping_cost, 2),
            "budget_usage_percent": round(self.budget_usage_percent, 1),
        }


def _money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _aggregate_key(canonical: str, unit: str, aggregatable: bool, display: str) -> str:
    if not aggregatable:
        return f"{canonical}::{display}::{unit}"
    return f"{canonical}::{unit}"


def compute_recipe_cost(menu: MenuPlan) -> Decimal:
    """Linear cost of exact merged purchase quantities (no package ceil)."""
    price_hints = extract_price_hints(menu.basket)
    contributions, _warnings = get_active_ingredient_contributions(menu)

    merged: OrderedDict[str, tuple[str, Decimal | None, str, bool]] = OrderedDict()

    for contribution in contributions:
        ingredient = contribution.ingredient
        name = ingredient.name.strip()
        if not name or _is_pantry_staple(name):
            continue

        parsed = parse_amount(ingredient.amount)
        canonical = canonical_ingredient_name(name)
        display = display_ingredient_name(name)
        key = _aggregate_key(canonical, parsed.unit, parsed.aggregatable, display)
        existing = merged.get(key)
        if existing is None:
            merged[key] = (display, parsed.quantity, parsed.unit, parsed.aggregatable)
            continue
        prev_display, prev_qty, prev_unit, prev_agg = existing
        if (
            parsed.aggregatable
            and prev_agg
            and parsed.quantity is not None
            and prev_qty is not None
        ):
            combined = merge_quantities(prev_qty, prev_unit, parsed.quantity, parsed.unit)
            if combined is not None:
                merged[key] = (prev_display, combined[0], combined[1], True)

    total = Decimal("0")
    for canonical_unit_key, (display, quantity, unit, aggregatable) in merged.items():
        canonical = canonical_unit_key.split("::", 1)[0]
        weight = format_weight(
            quantity,
            unit if aggregatable else "unknown",
            raw_fallback="" if aggregatable else "по вкусу",
        )
        price, _source = estimate_line_price(
            canonical_name=canonical,
            display_name=display,
            weight=weight,
            price_hints=price_hints,
        )
        if price is not None:
            total += price

    return _money(total)


def compute_budget_utilization(
    menu: MenuPlan,
    budget_limit: float,
) -> BudgetUtilization | None:
    """Derive dual costs and usage percent. None if budget is not usable."""
    if not math.isfinite(budget_limit) or budget_limit <= 0:
        return None

    shopping = _money(max(Decimal("0"), Decimal(str(menu.total_cost))))

    try:
        recipe = compute_recipe_cost(menu)
    except Exception:
        logger.exception("recipe_cost_compute_failed")
        recipe = shopping

    # Prefer shopping as ceiling when linear estimate overshoots (shared packs).
    if recipe > shopping and shopping > 0:
        recipe = shopping

    usage = float(shopping / Decimal(str(budget_limit)) * Decimal("100"))
    pack_gap = float(_money(shopping - recipe))
    ratio = shopping / Decimal(str(budget_limit))

    return BudgetUtilization(
        budget_limit=float(Decimal(str(budget_limit))),
        recipe_cost=float(recipe),
        shopping_cost=float(shopping),
        budget_usage_percent=round(usage, 1),
        pack_gap=pack_gap,
        in_target_range=TARGET_USAGE_MIN <= ratio <= TARGET_USAGE_MAX,
        underutilized=ratio < TARGET_USAGE_MIN,
    )


def build_budget_utilization_explanation(utilization: BudgetUtilization) -> str:
    """Human-readable StrategyExplanation-style blurb."""
    lines = [
        f"Использовано {utilization.budget_usage_percent:g}% бюджета "
        f"({_format_rub(utilization.shopping_cost)} ₽ из {_format_rub(utilization.budget_limit)} ₽)."
    ]
    if utilization.pack_gap > 0.5:
        lines.append(
            "Стоимость покупки выше стоимости рецептов, "
            "так как часть продуктов приобретается полными упаковками."
        )
    elif utilization.underutilized:
        lines.append(
            "Бюджет использован ниже целевого диапазона 90–100%; "
            "ограничения профиля могли не позволить потратить больше без потери качества."
        )
    return " ".join(lines)


def _format_rub(amount: float) -> str:
    return f"{amount:,.0f}".replace(",", " ")


def build_budget_optimizer_prompt(
    *,
    budget_limit: float,
    shopping_cost: float,
    usage_percent: float,
) -> str:
    """Targeted soft upgrade — not a full menu rebuild."""
    gap = max(0.0, float(budget_limit) * 0.90 - float(shopping_cost))
    return (
        "\n\n═══ BUDGET OPTIMIZER (мягкое улучшение) ═══\n"
        f"Текущая стоимость покупки (shopping_cost) ≈ {shopping_cost:.0f} ₽ "
        f"при бюджете {budget_limit:.0f} ₽ ({usage_percent:.0f}% использования).\n"
        "Целевой диапазон: 90–100% бюджета.\n"
        f"Недостаёт примерно {gap:.0f} ₽ до нижней границы 90%.\n\n"
        "Улучши КАЧЕСТВО ингредиентов в существующих блюдах, не перестраивая меню:\n"
        "- более качественная рыба/мясо, сыр, овощи, ягоды, крупы — где уместно;\n"
        "- сохрани число дней, meal_types, leftovers, cook_days, повторы;\n"
        "- НЕ добавляй блюда только чтобы потратить деньги;\n"
        "- НЕ увеличивай порции искусственно;\n"
        "- НЕ ухудшай разнообразие и НЕ нарушай аллергии/исключения/время готовки;\n"
        "- НЕ превышай бюджет (total_cost корзины ≤ budget).\n"
        "Верни полный исправленный JSON меню.\n"
    )
