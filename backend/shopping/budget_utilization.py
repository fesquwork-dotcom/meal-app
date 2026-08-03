"""Budget utilization + Budget Optimizer helpers (Sprint 10.5.4 / 10.5.5 / 10.8).

Cost semantics (Sprint 10.8):
- model_total: Claude self-estimate. Never authoritative for weekly budget.
- recipe_cost / calculated_total: recipe / pre-rebuild basket arithmetic. Diagnostic.
- shopping_cost: BasketEngine normalized purchase cost. AUTHORITATIVE for
  BUDGET_EXCEEDED and budget_usage_percent.
- After BasketEngine rebuild, MenuPlan.total_cost holds shopping_cost (wire compat).

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
TARGET_USAGE_PREFERRED = Decimal("0.95")
TARGET_USAGE_MAX = Decimal("1.00")

# Soft quality-upgrade passes after the first valid underutilized menu.
MAX_BUDGET_OPTIMIZER_CORRECTIONS = 2

# Stop when a valid candidate improves usage by less than this many points
# without entering the 90–100% band.
NEGLIGIBLE_USAGE_IMPROVEMENT_POINTS = 1.0

_MONEY_EPS = Decimal("0.01")


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


@dataclass(frozen=True)
class BudgetOptimizationTarget:
    """Bounded correction target derived from shopping_cost authority."""

    budget_limit: float
    current_cost: float
    usage_percent: float
    min_target: float
    preferred_target: float
    max_target: float
    desired_delta: float

    @property
    def underutilized(self) -> bool:
        return self.current_cost < self.min_target - float(_MONEY_EPS)

    @property
    def in_target_range(self) -> bool:
        return (
            self.min_target - float(_MONEY_EPS)
            <= self.current_cost
            <= self.max_target + float(_MONEY_EPS)
        )


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


def shopping_cost_from_menu(menu: MenuPlan | dict) -> float:
    """Authoritative basket cost: MenuPlan.total_cost after BasketEngine rebuild."""
    if isinstance(menu, dict):
        raw = menu.get("shopping_cost", menu.get("total_cost", 0))
    else:
        raw = menu.total_cost
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(value) or value < 0:
        return 0.0
    return float(_money(Decimal(str(value))))


def usage_percent_from_shopping(shopping_cost: float, budget_limit: float) -> float:
    if not math.isfinite(budget_limit) or budget_limit <= 0:
        return 0.0
    return round(float(Decimal(str(shopping_cost)) / Decimal(str(budget_limit)) * 100), 1)


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


def compute_budget_optimization_target(
    shopping_cost: float,
    budget_limit: float,
) -> BudgetOptimizationTarget | None:
    if not math.isfinite(budget_limit) or budget_limit <= 0:
        return None
    if not math.isfinite(shopping_cost) or shopping_cost < 0:
        return None

    limit = Decimal(str(budget_limit))
    current = _money(Decimal(str(shopping_cost)))
    min_target = _money(limit * TARGET_USAGE_MIN)
    preferred = _money(limit * TARGET_USAGE_PREFERRED)
    max_target = _money(limit)
    desired = preferred - current
    if desired < 0:
        desired = Decimal("0")

    return BudgetOptimizationTarget(
        budget_limit=float(limit),
        current_cost=float(current),
        usage_percent=usage_percent_from_shopping(float(current), float(limit)),
        min_target=float(min_target),
        preferred_target=float(preferred),
        max_target=float(max_target),
        desired_delta=float(desired),
    )


def should_start_budget_optimizer(shopping_cost: float, budget_limit: float) -> bool:
    target = compute_budget_optimization_target(shopping_cost, budget_limit)
    return bool(target and target.underutilized)


def is_shopping_in_target(shopping_cost: float, budget_limit: float) -> bool:
    target = compute_budget_optimization_target(shopping_cost, budget_limit)
    return bool(target and target.in_target_range)


def is_shopping_within_budget(shopping_cost: float, budget_limit: float) -> bool:
    return float(shopping_cost) <= float(budget_limit) + float(_MONEY_EPS)


def _distance_to_preferred(shopping_cost: float, budget_limit: float) -> float:
    preferred = float(budget_limit) * float(TARGET_USAGE_PREFERRED)
    return abs(float(shopping_cost) - preferred)


def is_better_budget_candidate(
    *,
    candidate_shopping: float,
    baseline_shopping: float,
    budget_limit: float,
) -> bool:
    """True when candidate is a safer/closer utilization than baseline."""
    if not is_shopping_within_budget(candidate_shopping, budget_limit):
        return False
    if not is_shopping_within_budget(baseline_shopping, budget_limit):
        return True

    cand_in = is_shopping_in_target(candidate_shopping, budget_limit)
    base_in = is_shopping_in_target(baseline_shopping, budget_limit)
    if cand_in and not base_in:
        return True
    if base_in and not cand_in:
        return False

    cand_dist = _distance_to_preferred(candidate_shopping, budget_limit)
    base_dist = _distance_to_preferred(baseline_shopping, budget_limit)
    if cand_dist + float(_MONEY_EPS) < base_dist:
        return True
    return False


def improvement_is_negligible(
    *,
    previous_shopping: float,
    new_shopping: float,
    budget_limit: float,
) -> bool:
    """True when usage barely moved and still outside the target band."""
    if is_shopping_in_target(new_shopping, budget_limit):
        return False
    prev_u = usage_percent_from_shopping(previous_shopping, budget_limit)
    new_u = usage_percent_from_shopping(new_shopping, budget_limit)
    return abs(new_u - prev_u) < NEGLIGIBLE_USAGE_IMPROVEMENT_POINTS


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
    usage_percent: float | None = None,
    target: BudgetOptimizationTarget | None = None,
    feedback: str | None = None,
    previous_model_total: float | None = None,
) -> str:
    """Bounded soft upgrade — quality/diversity, not artificial spending."""
    resolved = target or compute_budget_optimization_target(shopping_cost, budget_limit)
    if resolved is None:
        resolved = BudgetOptimizationTarget(
            budget_limit=float(budget_limit),
            current_cost=float(shopping_cost),
            usage_percent=float(usage_percent or 0),
            min_target=float(budget_limit) * 0.90,
            preferred_target=float(budget_limit) * 0.95,
            max_target=float(budget_limit),
            desired_delta=max(0.0, float(budget_limit) * 0.95 - float(shopping_cost)),
        )

    usage = float(usage_percent) if usage_percent is not None else resolved.usage_percent

    model_note = ""
    if previous_model_total is not None and math.isfinite(previous_model_total):
        model_note = (
            f"Предыдущее меню оценило себя (model_total / total_cost) примерно в "
            f"{previous_model_total:.0f} ₽, но нормализованная корзина BasketEngine "
            f"стоит только {resolved.current_cost:.2f} ₽. "
            "Игнорируй предыдущую самооценку total_cost для оптимизации бюджета — "
            "ориентируйся только на shopping_cost ниже.\n"
        )

    body = (
        "\n\n═══ BUDGET OPTIMIZER (мягкое улучшение качества) ═══\n"
        "Авторитетная стоимость — нормализованная корзина (shopping_cost / BasketEngine), "
        "НЕ model_total и НЕ сумма оценок блюд / recipe_cost.\n"
        f"{model_note}"
        f"Текущий shopping_cost = {resolved.current_cost:.2f} ₽ "
        f"({usage:.1f}% от бюджета {resolved.budget_limit:.2f} ₽).\n"
        f"Допустимый диапазон: {resolved.min_target:.2f}–{resolved.max_target:.2f} ₽ "
        f"(90–100%).\n"
        f"Предпочтительная цель ≈ {resolved.preferred_target:.2f} ₽ (~95%).\n"
        f"Желаемый прирост shopping_cost ≈ {resolved.desired_delta:.2f} ₽ "
        f"(не обязателен, если ограничения не позволяют).\n\n"
        "НИКОГДА не превышай budget_limit по shopping_cost после пересборки корзины. "
        "Не пытайся «добить» бюджет через своё поле total_cost — backend пересчитает "
        "покупную корзину независимо.\n\n"
        "Улучши КАЧЕСТВО и разнообразие ингредиентов в существующих блюдах:\n"
        "- более качественные белки (рыба/мясо), сыр, овощи, ягоды, орехи/семена, "
        "крупы — где уместно кулинарно и по предпочтениям;\n"
        "- замени излишне дешёвые ингредиенты на лучшие альтернативы без смены структуры меню.\n\n"
        "СТРОГО сохрани структуру:\n"
        "- meal_id, recipe_id, requires_cooking, prepared_on_day;\n"
        "- uses_leftovers, source_meal_id, batch/leftover связи;\n"
        "- число дней, meal_types, cook_days, shopping_days, повторы;\n"
        "- аллергии/исключения/время готовки/strategy constraints.\n"
        "Если меняешь ингредиент source-блюда с leftovers — зависимые leftover-блюда "
        "должны остаться валидными (не допускай LEFTOVER_SOURCE_INGREDIENT_MISSING).\n\n"
        "ЗАПРЕЩЕНО:\n"
        "- добавлять блюда только чтобы потратить деньги;\n"
        "- увеличивать порции искусственно;\n"
        "- добавлять лишние ингредиенты без кулинарной причины;\n"
        "- менять days/persons/meal_types;\n"
        "- разрушать batch cooking / leftovers.\n"
        "Верни полный исправленный JSON меню.\n"
    )
    if feedback:
        body += "\n" + feedback.strip() + "\n"
    return body


def build_budget_optimizer_feedback(
    *,
    budget_limit: float,
    previous_shopping_cost: float | None,
    issue_codes: list[str] | None = None,
    overshoot_amount: float | None = None,
    reason: str = "rejected",
) -> str:
    """Feedback for the next bounded optimizer correction."""
    lines = [
        "═══ BUDGET OPTIMIZER FEEDBACK (предыдущий кандидат отклонён) ═══",
        f"Причина: {reason}.",
        f"Бюджет: {budget_limit:.2f} ₽. Цель по-прежнему 90–100%, предпочтительно ~95%.",
    ]
    if previous_shopping_cost is not None:
        lines.append(
            f"shopping_cost предыдущего кандидата ≈ {previous_shopping_cost:.2f} ₽ "
            f"({usage_percent_from_shopping(previous_shopping_cost, budget_limit):.1f}%)."
        )
    if overshoot_amount is not None and overshoot_amount > 0:
        lines.append(
            f"Перерасход относительно бюджета ≈ {overshoot_amount:.2f} ₽. "
            "Снизь shopping_cost, сохранив улучшения качества где возможно."
        )
    if issue_codes:
        codes = ", ".join(str(code) for code in issue_codes[:12])
        lines.append(f"Коды валидации: {codes}.")
        if any("LEFTOVER" in str(code).upper() for code in issue_codes):
            lines.append(
                "Сохрани leftover/source_meal_id и ингредиенты source-блюд "
                "для всех uses_leftovers=true."
            )
    lines.append(
        "Сделай ОДИН bounded correction: цель 90–100% shopping_cost, "
        "без превышения бюджета и без поломки leftover-связей."
    )
    return "\n".join(lines)
