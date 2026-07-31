"""Deterministic basket rebuild from MenuPlan recipes."""

from __future__ import annotations

import logging
import re
import time
from collections import OrderedDict
from decimal import Decimal, InvalidOperation

from dataclasses import dataclass

from menu_models import BasketCategory, BasketItem, MenuPlan
from menu_validation import _is_pantry_staple
from recipe_identity import effective_contribution, meal_has_contribution_roles, resolve_recipe_for_meal
from shopping.exceptions import BasketPriceUnavailableError
from shopping.models import (
    BasketBuildResult,
    BasketBuildWarning,
    CrossUnitMergeTrace,
    NormalizedIngredient,
)
from shopping.normalization import canonical_ingredient_name, display_ingredient_name
from shopping.pricing import estimate_line_price, extract_price_hints
from shopping.recipe_selection import get_active_ingredient_contributions
from shopping.shopping_advice import purchase_badges, shopping_advice_for
from shopping.units import (
    DEFAULT_UNIT_POLICY,
    CanonicalUnitPolicy,
    convert_to_base,
    format_decimal_plain,
    format_quantity_human,
    format_weight,
    merge_quantities,
    parse_amount,
)

logger = logging.getLogger(__name__)

MAX_RECIPES = 200
MAX_INGREDIENTS_PER_RECIPE = 100
MAX_PRODUCT_NAME_LENGTH = 120
DEFAULT_CATEGORY = "Прочее"

_CATEGORY_HINTS: dict[str, str] = {
    "курин": "Мясо",
    "говядин": "Мясо",
    "свинин": "Мясо",
    "индейк": "Мясо",
    "фарш": "Мясо",
    "рыб": "Рыба",
    "лосос": "Рыба",
    "треск": "Рыба",
    "тунц": "Рыба",
    "кревет": "Рыба",
    "молок": "Молочные продукты",
    "творог": "Молочные продукты",
    "сыр": "Молочные продукты",
    "яйц": "Молочные продукты",
    "сметан": "Молочные продукты",
    "йогурт": "Молочные продукты",
    "кефир": "Молочные продукты",
    "сливк": "Молочные продукты",
    "овощ": "Овощи",
    "помидор": "Овощи",
    "томат": "Овощи",
    "огурец": "Овощи",
    "морков": "Овощи",
    "картоф": "Овощи",
    "лук": "Овощи",
    "чеснок": "Овощи",
    "капуст": "Овощи",
    "перец болгар": "Овощи",
    "болгарск": "Овощи",
    "кабач": "Овощи",
    "баклажан": "Овощи",
    "шпинат": "Овощи",
    "гриб": "Овощи",
    "шампиньон": "Овощи",
    "зелен": "Овощи",
    "укроп": "Овощи",
    "петрушк": "Овощи",
    "лимон": "Овощи",
    "авокадо": "Овощи",
    "круп": "Крупы",
    "рис": "Крупы",
    "греч": "Крупы",
    "овсян": "Крупы",
    "булгур": "Крупы",
    "киноа": "Крупы",
    "нут": "Крупы",
    "чечевиц": "Крупы",
    "макарон": "Крупы",
    "паста": "Крупы",
    "мук": "Бакалея",
    "сахар": "Бакалея",
    "хлеб": "Бакалея",
    "паприк": "Специи",
    "кумин": "Специи",
    "кориандр": "Специи",
    "куркум": "Специи",
    "орегано": "Специи",
    "базилик": "Специи",
    "кориц": "Специи",
    "ваниль": "Специи",
    "перец черн": "Специи",
    "перец чёрн": "Специи",
    "чёрный перец": "Специи",
    "черный перец": "Специи",
    "соус": "Соусы",
    "тахини": "Соусы",
    "уксус": "Соусы",
    "майонез": "Соусы",
    "горчиц": "Соусы",
    "кетчуп": "Соусы",
}


# QA guard: no basket text may carry exponent/NaN/Infinity artifacts (Sprint 10.5.1).
_SCIENTIFIC_NUMBER_PATTERN = re.compile(r"\d+(?:[.,]\d+)?[eE][+-]?\d+")


def _has_unsafe_number_text(text: str) -> bool:
    if _SCIENTIFIC_NUMBER_PATTERN.search(text):
        return True
    return any(marker in text for marker in ("NaN", "Infinity"))


def _safe_number_text(text: str) -> str:
    """Rewrites scientific-notation tokens to fixed-point; drops NaN/Infinity."""

    def _rewrite(match: re.Match[str]) -> str:
        token = match.group(0).replace(",", ".")
        try:
            return format_decimal_plain(Decimal(token))
        except InvalidOperation:
            return ""

    cleaned = _SCIENTIFIC_NUMBER_PATTERN.sub(_rewrite, text)
    cleaned = cleaned.replace("NaN", "").replace("Infinity", "")
    return re.sub(r"\s+", " ", cleaned).strip()


def _sanitize_basket_text(basket: list[BasketCategory]) -> list[BasketCategory]:
    """Last-line defense: no scientific notation may reach the wire format."""
    sanitized: list[BasketCategory] = []
    for category in basket:
        category_name = category.category
        if _has_unsafe_number_text(category_name):
            logger.error(
                "basket_text_unsafe field=category value=%r", category_name
            )
            category_name = _safe_number_text(category_name)

        items: list[BasketItem] = []
        for item in category.items:
            updates: dict[str, object] = {}
            for field in ("name", "weight"):
                value = getattr(item, field)
                if _has_unsafe_number_text(value):
                    logger.error(
                        "basket_text_unsafe field=%s value=%r", field, value
                    )
                    updates[field] = _safe_number_text(value)
            for field in ("shopping_advice", "badges"):
                values = getattr(item, field)
                if any(_has_unsafe_number_text(value) for value in values):
                    logger.error(
                        "basket_text_unsafe field=%s value=%r", field, values
                    )
                    updates[field] = [_safe_number_text(value) for value in values]
            items.append(item.model_copy(update=updates) if updates else item)

        sanitized.append(BasketCategory(category=category_name, items=items))
    return sanitized


def _guess_category(display_name: str, existing_hints: dict[str, str]) -> str:
    key = canonical_ingredient_name(display_name)
    if key in existing_hints:
        hinted = existing_hints[key]
        # Normalize legacy "Молочное" / "Продукты" labels.
        if hinted.lower() in {"молочное", "молочные"}:
            return "Молочные продукты"
        if hinted.lower() in {"продукты", "прочее", "другое"}:
            return DEFAULT_CATEGORY
        return hinted
    lowered = display_name.lower()
    for fragment, category in _CATEGORY_HINTS.items():
        if fragment in lowered or fragment in key:
            return category
    return DEFAULT_CATEGORY


def _aggregate_key(ingredient: NormalizedIngredient) -> str:
    if not ingredient.aggregatable:
        return f"{ingredient.canonical_name}::{ingredient.display_name}::{ingredient.unit}"
    return f"{ingredient.canonical_name}::{ingredient.unit}"


def _collect_normalized_ingredients(
    menu: MenuPlan,
    unit_policy: CanonicalUnitPolicy,
) -> tuple[list[NormalizedIngredient], list[BasketBuildWarning], int]:
    contributions, warnings = get_active_ingredient_contributions(menu)
    purchase_count = 0
    from_source_count = 0
    pantry_count = 0

    for day_index, day in enumerate(menu.days_plan):
        for meal in day.meals:
            recipe, _ = resolve_recipe_for_meal(
                meal, menu.recipes, path=f"days_plan[{day_index}]"
            )
            if recipe is None:
                continue
            if meal.uses_leftovers and not meal_has_contribution_roles(recipe):
                continue
            for ingredient in recipe.ingredients:
                role = effective_contribution(meal, ingredient)
                if role == "purchase":
                    purchase_count += 1
                elif role == "from_source":
                    from_source_count += 1
                elif role == "pantry":
                    pantry_count += 1

    if len(menu.recipes) > MAX_RECIPES:
        warnings.append(
            BasketBuildWarning(
                code="BASKET_RECIPE_NOT_FOUND",
                message=f"Recipe count exceeds limit {MAX_RECIPES}",
                path="recipes",
            )
        )

    raw: list[NormalizedIngredient] = []
    for contribution in contributions:
        recipe = contribution.recipe
        ingredient = contribution.ingredient
        if len(recipe.ingredients) > MAX_INGREDIENTS_PER_RECIPE:
            warnings.append(
                BasketBuildWarning(
                    code="BASKET_INVALID_QUANTITY",
                    message=f"Recipe '{recipe.name}' exceeds ingredient limit",
                    path="recipes",
                )
            )
            continue

        meal_id = contribution.meal.meal_id or f"day{contribution.day_index + 1}_{contribution.meal.type}"
        name = ingredient.name.strip()[:MAX_PRODUCT_NAME_LENGTH]
        if not name:
            continue
        parsed = parse_amount(ingredient.amount)
        recipe_key = recipe.recipe_id or recipe.name
        canonical = canonical_ingredient_name(name)
        # Sprint 10.5.2 extension point: default policy returns the unit unchanged.
        resolved_unit = unit_policy.resolve_unit(canonical, parsed.unit)
        raw.append(
            NormalizedIngredient(
                canonical_name=canonical,
                display_name=display_ingredient_name(name),
                quantity=parsed.quantity,
                unit=resolved_unit,
                aggregatable=parsed.aggregatable,
                source_recipe_names=(recipe_key,),
                source_meal_ids=(meal_id,),
            )
        )
        if not parsed.aggregatable:
            warnings.append(
                BasketBuildWarning(
                    code="BASKET_NON_AGGREGATABLE",
                    message=f"Non-aggregatable amount '{ingredient.amount}' for '{name}'",
                    path=None,
                )
            )

    logger.info(
        "basket_contributions purchase=%s from_source=%s pantry=%s",
        purchase_count,
        from_source_count,
        pantry_count,
    )
    return raw, warnings, len(raw)


def _merge_ingredients(raw: list[NormalizedIngredient]) -> tuple[OrderedDict[str, NormalizedIngredient], int]:
    merged: OrderedDict[str, NormalizedIngredient] = OrderedDict()
    duplicate_merges = 0

    for item in raw:
        key = _aggregate_key(item)
        existing = merged.get(key)
        if existing is None:
            merged[key] = item
            continue

        duplicate_merges += 1
        if not item.aggregatable or not existing.aggregatable:
            # Keep separate non-aggregatable lines by unique key above.
            continue

        if item.quantity is None or existing.quantity is None:
            merged[key] = NormalizedIngredient(
                canonical_name=existing.canonical_name,
                display_name=existing.display_name,
                quantity=None,
                unit=existing.unit,
                aggregatable=False,
                source_recipe_names=existing.source_recipe_names + item.source_recipe_names,
                source_meal_ids=existing.source_meal_ids + item.source_meal_ids,
            )
            continue

        merged_qty = merge_quantities(
            existing.quantity,
            existing.unit or "unknown",
            item.quantity,
            item.unit or "unknown",
        )
        if merged_qty is None:
            continue

        merged[key] = NormalizedIngredient(
            canonical_name=existing.canonical_name,
            display_name=existing.display_name,
            quantity=merged_qty[0],
            unit=merged_qty[1],
            aggregatable=True,
            source_recipe_names=existing.source_recipe_names + item.source_recipe_names,
            source_meal_ids=existing.source_meal_ids + item.source_meal_ids,
        )

    return merged, duplicate_merges


@dataclass
class _ProductRow:
    """One priced basket line before the final canonical_name merge."""

    canonical_name: str
    display_name: str
    quantity: Decimal | None
    unit: str
    aggregatable: bool
    fallback_text: str
    price: Decimal
    category: str
    source_recipe_names: tuple[str, ...]
    source_meal_ids: tuple[str, ...]


# Stable part ordering for composite weights: "13 шт + 800 г + по вкусу".
_COMPOSITE_UNIT_ORDER = {"pcs": 0, "package": 1, "g": 2, "ml": 3, "tbsp": 4, "tsp": 5}


def _group_base_amounts(rows: list[_ProductRow]) -> tuple[dict[str, Decimal], list[str]]:
    """Sums aggregatable quantities per base unit; collects unique fallback texts."""
    amounts: dict[str, Decimal] = {}
    texts: list[str] = []
    for row in rows:
        base = (
            convert_to_base(row.quantity, row.unit)
            if row.aggregatable and row.quantity is not None
            else None
        )
        if base is not None:
            amounts[base[1]] = amounts.get(base[1], Decimal("0")) + base[0]
        elif row.fallback_text and row.fallback_text not in texts:
            texts.append(row.fallback_text)
    return amounts, texts


def _composite_weight(amounts: dict[str, Decimal], texts: list[str]) -> str:
    ordered_units = sorted(amounts.keys(), key=lambda unit: (_COMPOSITE_UNIT_ORDER.get(unit, 9), unit))
    chunks = [format_quantity_human(amounts[unit], unit) for unit in ordered_units]
    chunks.extend(texts)
    return " + ".join(chunk for chunk in chunks if chunk)


def _merge_group_weight(
    canonical_name: str,
    rows: list[_ProductRow],
    unit_policy: CanonicalUnitPolicy,
) -> tuple[str, CrossUnitMergeTrace | None]:
    """Resolves the display weight for all rows sharing one canonical_name."""
    amounts, texts = _group_base_amounts(rows)

    negative_units = [unit for unit, qty in amounts.items() if qty < 0]
    if negative_units:
        logger.error(
            "basket_invalid_quantity canonical_name=%s units=%s", canonical_name, negative_units
        )
        amounts = {unit: qty for unit, qty in amounts.items() if qty >= 0}

    source_units = tuple(row.unit for row in rows)
    source_quantities = tuple(
        format_decimal_plain(row.quantity) if row.quantity is not None else (row.fallback_text or "?")
        for row in rows
    )

    if len(amounts) <= 1:
        # No cross-unit conflict: single dimension (+ optional to-taste texts).
        weight = _composite_weight(amounts, texts)
        return weight, None

    rule = unit_policy.rule_for(canonical_name)
    reason: str | None = None
    if set(amounts.keys()) != {"g", "pcs"}:
        reason = "incompatible_units"
    elif rule is None:
        reason = "no_rule"
    elif not rule.enabled:
        reason = "rule_disabled"
    elif rule.confidence == "unknown":
        reason = "confidence_unknown"
    elif rule.grams_per_piece is None or rule.grams_per_piece <= 0:
        reason = "no_grams_per_piece"

    if reason is None:
        assert rule is not None and rule.grams_per_piece is not None
        total_grams = amounts["g"] + amounts["pcs"] * rule.grams_per_piece
        weight = format_quantity_human(total_grams, "g", approximate=True)
        if texts:
            weight = " + ".join([weight, *texts])
        logger.info(
            "basket_cross_unit_merge_applied canonical_name=%s source_units=%s "
            "source_quantities=%s preferred_unit=%s grams_per_piece=%s confidence=%s "
            "result_quantity=%s source_count=%s",
            canonical_name,
            list(source_units),
            list(source_quantities),
            rule.preferred_unit,
            format_decimal_plain(rule.grams_per_piece),
            rule.confidence,
            format_decimal_plain(total_grams),
            len(rows),
        )
        return weight, CrossUnitMergeTrace(
            canonical_name=canonical_name,
            source_units=source_units,
            source_quantities=source_quantities,
            preferred_unit=rule.preferred_unit,
            grams_per_piece=format_decimal_plain(rule.grams_per_piece),
            confidence=rule.confidence,
            result_quantity=format_decimal_plain(total_grams),
            source_count=len(rows),
            applied=True,
        )

    weight = _composite_weight(amounts, texts)
    logger.info(
        "basket_cross_unit_merge_skipped canonical_name=%s reason=%s source_units=%s fallback_display=%r",
        canonical_name,
        reason,
        list(source_units),
        weight,
    )
    return weight, CrossUnitMergeTrace(
        canonical_name=canonical_name,
        source_units=source_units,
        source_quantities=source_quantities,
        preferred_unit=rule.preferred_unit if rule else None,
        grams_per_piece=(
            format_decimal_plain(rule.grams_per_piece)
            if rule and rule.grams_per_piece is not None
            else None
        ),
        confidence=rule.confidence if rule else None,
        result_quantity=None,
        source_count=len(rows),
        applied=False,
        reason=reason,
        fallback_display=weight,
    )


def _resolve_group_category(canonical_name: str, rows: list[_ProductRow]) -> str:
    categories = [row.category for row in rows if row.category]
    resolved = categories[0] if categories else DEFAULT_CATEGORY
    if len(set(categories)) > 1:
        logger.warning(
            "basket_category_conflict canonical_name=%s categories=%s resolved=%s",
            canonical_name,
            sorted(set(categories)),
            resolved,
        )
    return resolved


def build_basket_from_menu(
    menu: MenuPlan,
    *,
    existing_basket: list[BasketCategory] | None = None,
    require_all_prices: bool = False,
    unit_policy: CanonicalUnitPolicy | None = None,
) -> BasketBuildResult:
    """Builds basket deterministically from active recipe ingredients."""
    started = time.monotonic()
    hint_source = existing_basket if existing_basket is not None else menu.basket
    price_hints = extract_price_hints(hint_source)

    category_hints: dict[str, str] = {}
    for category in hint_source:
        for item in category.items:
            category_hints[canonical_ingredient_name(item.name)] = category.category

    resolved_policy = unit_policy or DEFAULT_UNIT_POLICY
    raw, warnings, raw_count = _collect_normalized_ingredients(menu, resolved_policy)
    merged, duplicate_merges = _merge_ingredients(raw)

    unresolved: list[str] = []
    rows_by_canonical: OrderedDict[str, list[_ProductRow]] = OrderedDict()

    for ingredient in merged.values():
        if _is_pantry_staple(ingredient.display_name):
            continue

        # Legacy per-line weight: pricing input and non-aggregatable fallback text.
        line_weight = format_weight(
            ingredient.quantity,
            ingredient.unit or "unknown",
            raw_fallback="по вкусу" if ingredient.unit == "to_taste" else "",
        )
        price, source = estimate_line_price(
            canonical_name=ingredient.canonical_name,
            display_name=ingredient.display_name,
            weight=line_weight,
            price_hints=price_hints,
        )

        if price is None:
            unresolved.append(ingredient.display_name)
            if require_all_prices:
                continue
            price = Decimal("0")
            warnings.append(
                BasketBuildWarning(
                    code="BASKET_PRICE_UNAVAILABLE",
                    message=f"No price hint for '{ingredient.display_name}'",
                    path=None,
                )
            )
        elif source == "estimated":
            warnings.append(
                BasketBuildWarning(
                    code="BASKET_PRICE_ESTIMATED",
                    message=f"Estimated price for '{ingredient.display_name}'",
                    path=None,
                )
            )

        rows_by_canonical.setdefault(ingredient.canonical_name, []).append(
            _ProductRow(
                canonical_name=ingredient.canonical_name,
                display_name=ingredient.display_name,
                quantity=ingredient.quantity,
                unit=ingredient.unit or "unknown",
                aggregatable=ingredient.aggregatable,
                fallback_text="по вкусу" if ingredient.unit == "to_taste" else "",
                price=price,
                category=_guess_category(ingredient.display_name, category_hints),
                source_recipe_names=ingredient.source_recipe_names,
                source_meal_ids=ingredient.source_meal_ids,
            )
        )

    if require_all_prices and unresolved:
        raise BasketPriceUnavailableError(unresolved)

    # Final stage (Sprint 10.5.2): exactly one BasketItem per canonical_name.
    cross_unit_traces: list[CrossUnitMergeTrace] = []
    category_items: dict[str, list[BasketItem]] = {}

    for canonical_name, rows in rows_by_canonical.items():
        weight, trace = _merge_group_weight(canonical_name, rows, resolved_policy)
        if trace is not None:
            cross_unit_traces.append(trace)
            if not trace.applied:
                warnings.append(
                    BasketBuildWarning(
                        code="BASKET_INCOMPATIBLE_UNITS",
                        message=(
                            f"Cross-unit merge fallback for '{rows[0].display_name}': "
                            f"{trace.reason}"
                        ),
                        path=None,
                    )
                )

        total_price = sum((row.price for row in rows), Decimal("0"))
        if total_price < 0:
            logger.error(
                "basket_invalid_price canonical_name=%s price=%s", canonical_name, total_price
            )
            total_price = Decimal("0")

        # Dedupe recipe/meal references so merged rows never double-count usage.
        unique_recipes: list[str] = []
        for row in rows:
            for recipe_key in row.source_recipe_names:
                if recipe_key and recipe_key not in unique_recipes:
                    unique_recipes.append(recipe_key)
        used_in = max(1, len(unique_recipes))

        display_name = rows[0].display_name
        category_name = _resolve_group_category(canonical_name, rows)
        advice = shopping_advice_for(display_name, category_name)
        badges = purchase_badges(used_in_recipes=used_in, shopping_advice=advice)
        basket_item = BasketItem(
            name=display_name,
            weight=weight,
            price=float(total_price),
            used_in_recipes=used_in,
            shopping_advice=advice,
            badges=badges,
        )
        category_items.setdefault(category_name, []).append(basket_item)

    basket: list[BasketCategory] = []
    for category_name in sorted(category_items.keys()):
        items = sorted(category_items[category_name], key=lambda item: item.name.lower())
        basket.append(BasketCategory(category=category_name, items=items))

    if not basket:
        basket = [
            BasketCategory(
                category=DEFAULT_CATEGORY,
                items=[BasketItem(name="Продукты", weight="", price=0.0)],
            )
        ]

    basket = _sanitize_basket_text(basket)

    # Safety contract: one canonical_name per basket. Log loudly, never drop silently.
    seen_canonicals: set[str] = set()
    for category in basket:
        for item in category.items:
            key = canonical_ingredient_name(item.name)
            if key in seen_canonicals:
                logger.error(
                    "basket_duplicate_canonical canonical_name=%s item=%r", key, item.name
                )
            seen_canonicals.add(key)

    total = Decimal(str(sum(item.price for category in basket for item in category.items)))
    total = total.quantize(Decimal("0.01"))

    duration_ms = int((time.monotonic() - started) * 1000)
    line_count = sum(len(category.items) for category in basket)
    logger.info(
        "basket_rebuild recipes=%s raw_ingredients=%s basket_lines=%s merged_duplicates=%s "
        "cross_unit_merges=%s unresolved_prices=%s total_cost=%s duration_ms=%s",
        len(menu.recipes),
        raw_count,
        line_count,
        duplicate_merges,
        sum(1 for trace in cross_unit_traces if trace.applied),
        len(unresolved),
        total,
        duration_ms,
    )

    return BasketBuildResult(
        basket=basket,
        total_cost=total,
        warnings=warnings,
        unresolved_prices=unresolved,
        merged_duplicate_count=duplicate_merges,
        raw_ingredient_count=raw_count,
        basket_line_count=line_count,
        cross_unit_merges=cross_unit_traces,
    )
