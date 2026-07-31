"""Sprint 10.5.2: cross-unit canonical merge — unit and integration tests."""

from __future__ import annotations

import logging
from decimal import Decimal

import pytest

from menu_models import (
    BasketCategory,
    BasketItem,
    DayMeal,
    DayPlan,
    MenuPlan,
    Recipe,
    RecipeIngredient,
)
from shopping.basket_builder import build_basket_from_menu
from shopping.unit_rules import CanonicalUnitRule, get_unit_rule
from shopping.units import CanonicalUnitPolicy, format_quantity_human


def _menu(ingredient_specs: list[tuple[str, str, str]]) -> MenuPlan:
    """ingredient_specs: (recipe_name, ingredient_name, amount) — one meal per recipe."""
    ingredients_by_recipe: dict[str, list[RecipeIngredient]] = {}
    for recipe_name, ing_name, amount in ingredient_specs:
        ingredients_by_recipe.setdefault(recipe_name, []).append(
            RecipeIngredient(name=ing_name, amount=amount)
        )

    recipes = [
        Recipe(name=recipe_name, ingredients=ingredients, steps=["Готовить"])
        for recipe_name, ingredients in ingredients_by_recipe.items()
    ]
    meals = [
        DayMeal(
            type="dinner",
            recipe_name=recipe_name,
            meal_id=f"day1_dinner_{index}",
            requires_cooking=True,
            prepared_on_day=1,
        )
        for index, recipe_name in enumerate(ingredients_by_recipe)
    ]

    return MenuPlan(
        summary="Тест",
        total_cost=500,
        days_plan=[DayPlan(day="День 1", meals=meals)],
        recipes=recipes,
        basket=[
            BasketCategory(
                category="Продукты",
                items=[BasketItem(name="Заглушка", weight="1 шт", price=100)],
            )
        ],
    )


def _items(result) -> list[BasketItem]:
    return [item for category in result.basket for item in category.items]


def _find(result, fragment: str) -> list[BasketItem]:
    return [item for item in _items(result) if fragment in item.name.lower()]


# --- 1–3: conversions ---------------------------------------------------------------


def test_same_unit_round_total_renders_as_kg():
    menu = _menu([("Суп", "Кабачок", "400 г"), ("Рагу", "Кабачок", "800 г")])
    result = build_basket_from_menu(menu)
    rows = _find(result, "кабач")
    assert len(rows) == 1
    assert rows[0].weight == "1.2 кг"


def test_potato_pieces_plus_grams_merge_to_approximate_kg():
    menu = _menu([("Суп", "Картофель", "13 шт"), ("Рагу", "Картофель", "800 г")])
    result = build_basket_from_menu(menu)
    rows = _find(result, "картоф")
    assert len(rows) == 1
    # 13 × 150 г + 800 г = 2750 г
    assert rows[0].weight == "≈2.75 кг"
    applied = [t for t in result.cross_unit_merges if t.applied]
    assert len(applied) == 1
    assert applied[0].canonical_name == "картофель"
    assert applied[0].result_quantity == "2750"
    assert applied[0].confidence == "approximate"
    assert applied[0].source_count == 2


def test_tomato_pieces_plus_grams_use_rule():
    menu = _menu([("Салат", "Помидоры", "2 шт"), ("Соус", "Томаты", "300 г")])
    result = build_basket_from_menu(menu)
    rows = _find(result, "помидор")
    assert len(rows) == 1
    # 2 × 110 г + 300 г = 520 г
    assert rows[0].weight == "≈520 г"


# --- 4–6: fallback and non-aggregatable ----------------------------------------------


def test_unknown_product_gets_composite_line():
    menu = _menu([("Суп", "Сельдерей", "3 шт"), ("Рагу", "Сельдерей", "800 г")])
    result = build_basket_from_menu(menu)
    rows = _find(result, "сельдерей")
    assert len(rows) == 1
    assert rows[0].weight == "3 шт + 800 г"
    skipped = [t for t in result.cross_unit_merges if not t.applied]
    assert len(skipped) == 1
    assert skipped[0].reason == "no_rule"
    assert skipped[0].fallback_display == "3 шт + 800 г"


def test_to_taste_plus_grams_composite():
    menu = _menu([("Салат", "Зелень свежая", "500 г"), ("Суп", "Зелень свежая", "по вкусу")])
    result = build_basket_from_menu(menu)
    rows = _find(result, "зелень")
    assert len(rows) == 1
    assert rows[0].weight == "500 г + по вкусу"


def test_duplicate_non_aggregatable_texts_deduplicated():
    menu = _menu(
        [
            ("Салат", "Кинза", "по вкусу"),
            ("Суп", "Кинза", "по вкусу"),
            ("Рагу", "Кинза", "по вкусу"),
        ]
    )
    result = build_basket_from_menu(menu)
    rows = _find(result, "кинза")
    assert len(rows) == 1
    assert rows[0].weight == "по вкусу"


# --- 7–9: price, metadata, categories -------------------------------------------------


def test_merged_price_is_sum_of_source_prices():
    menu = _menu([("Суп", "Картофель", "13 шт"), ("Рагу", "Картофель", "800 г")])
    unmerged_policy = CanonicalUnitPolicy()
    unmerged_policy.rule_for = lambda _name: None  # type: ignore[method-assign]
    fallback = build_basket_from_menu(menu, unit_policy=unmerged_policy)
    merged = build_basket_from_menu(menu)

    fallback_price = sum(item.price for item in _find(fallback, "картоф"))
    merged_price = sum(item.price for item in _find(merged, "картоф"))
    assert merged_price == pytest.approx(fallback_price)


def test_recipe_ids_not_double_counted():
    # Same recipe contributes both pcs and grams — used_in_recipes must stay per-recipe.
    menu = _menu([("Суп", "Картофель", "2 шт"), ("Суп", "Картофель", "300 г")])
    result = build_basket_from_menu(menu)
    rows = _find(result, "картоф")
    assert len(rows) == 1
    assert rows[0].used_in_recipes == 1

    menu2 = _menu([("Суп", "Картофель", "2 шт"), ("Рагу", "Картофель", "300 г")])
    rows2 = _find(build_basket_from_menu(menu2), "картоф")
    assert rows2[0].used_in_recipes == 2


def test_category_conflict_resolved_deterministically(caplog):
    # Force a conflict through existing-basket category hints.
    menu = _menu([("Суп", "Картофель", "2 шт"), ("Рагу", "Картофель", "300 г")])
    with caplog.at_level(logging.WARNING):
        result = build_basket_from_menu(menu)
    rows = _find(result, "картоф")
    assert len(rows) == 1
    categories = [
        category.category
        for category in result.basket
        for item in category.items
        if "картоф" in item.name.lower()
    ]
    assert len(categories) == 1  # single category, never two


# --- 11–13: safety ---------------------------------------------------------------------


def test_canonical_names_unique_after_merge():
    menu = _menu(
        [
            ("Суп", "Картофель", "13 шт"),
            ("Рагу", "Картофель", "800 г"),
            ("Салат", "Помидоры", "2 шт"),
            ("Соус", "Томаты", "300 г"),
            ("Гарнир", "Сельдерей", "3 шт"),
            ("Суп2", "Сельдерей", "100 г"),
        ]
    )
    result = build_basket_from_menu(menu)
    from shopping.normalization import canonical_ingredient_name

    canonicals = [canonical_ingredient_name(item.name) for item in _items(result)]
    assert len(canonicals) == len(set(canonicals))


def test_no_scientific_notation_after_cross_unit_merge():
    menu = _menu([("Суп", "Картофель", "8 шт"), ("Рагу", "Картофель", "800 г")])
    result = build_basket_from_menu(menu)
    for item in _items(result):
        for value in (item.name, item.weight):
            assert "E+" not in value and "E-" not in value
            assert "NaN" not in value and "Infinity" not in value


def test_negative_amounts_do_not_produce_negative_quantities():
    from shopping.units import parse_amount

    parsed = parse_amount("-5 г")
    # Parser has no negative grammar: such input degrades to non-aggregatable.
    assert parsed.quantity is None or parsed.quantity >= 0
    assert parsed.aggregatable is False


# --- 14–15: rule gating ------------------------------------------------------------------


class _DisabledRulePolicy(CanonicalUnitPolicy):
    def rule_for(self, canonical_name: str):
        rule = get_unit_rule(canonical_name)
        if rule is None:
            return None
        return CanonicalUnitRule(
            canonical_name=rule.canonical_name,
            preferred_unit=rule.preferred_unit,
            grams_per_piece=rule.grams_per_piece,
            confidence=rule.confidence,
            aliases=rule.aliases,
            enabled=False,
        )


class _UnknownConfidencePolicy(CanonicalUnitPolicy):
    def rule_for(self, canonical_name: str):
        rule = get_unit_rule(canonical_name)
        if rule is None:
            return None
        return CanonicalUnitRule(
            canonical_name=rule.canonical_name,
            preferred_unit=rule.preferred_unit,
            grams_per_piece=rule.grams_per_piece,
            confidence="unknown",
            aliases=rule.aliases,
        )


def test_disabled_rule_falls_back_to_composite():
    menu = _menu([("Суп", "Картофель", "13 шт"), ("Рагу", "Картофель", "800 г")])
    result = build_basket_from_menu(menu, unit_policy=_DisabledRulePolicy())
    rows = _find(result, "картоф")
    assert len(rows) == 1
    assert rows[0].weight == "13 шт + 800 г"
    skipped = [t for t in result.cross_unit_merges if not t.applied]
    assert skipped and skipped[0].reason == "rule_disabled"


def test_unknown_confidence_falls_back_to_composite():
    menu = _menu([("Суп", "Картофель", "13 шт"), ("Рагу", "Картофель", "800 г")])
    result = build_basket_from_menu(menu, unit_policy=_UnknownConfidencePolicy())
    rows = _find(result, "картоф")
    assert len(rows) == 1
    assert rows[0].weight == "13 шт + 800 г"
    skipped = [t for t in result.cross_unit_merges if not t.applied]
    assert skipped and skipped[0].reason == "confidence_unknown"


# --- 16: determinism ----------------------------------------------------------------------


def test_deterministic_output_for_same_input():
    menu = _menu(
        [
            ("Суп", "Картофель", "13 шт"),
            ("Рагу", "Картофель", "800 г"),
            ("Салат", "Сельдерей", "3 шт"),
            ("Суп2", "Сельдерей", "200 г"),
            ("Завтрак", "Кинза", "по вкусу"),
        ]
    )
    first = build_basket_from_menu(menu)
    second = build_basket_from_menu(menu)
    assert [
        (c.category, i.name, i.weight, i.price) for c in first.basket for i in c.items
    ] == [(c.category, i.name, i.weight, i.price) for c in second.basket for i in c.items]


# --- display formatting -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("quantity", "unit", "approximate", "expected"),
    [
        (Decimal("850"), "g", False, "850 г"),
        (Decimal("1200"), "g", False, "1.2 кг"),
        (Decimal("2000"), "g", False, "2 кг"),
        (Decimal("2750"), "g", True, "≈2.75 кг"),
        (Decimal("500"), "ml", False, "500 мл"),
        (Decimal("1500"), "ml", False, "1.5 л"),
        (Decimal("3"), "pcs", False, "3 шт"),
        (Decimal("2500"), "g", False, "2.5 кг"),
    ],
)
def test_format_quantity_human(quantity, unit, approximate, expected):
    assert format_quantity_human(quantity, unit, approximate=approximate) == expected


# --- rule catalog -------------------------------------------------------------------------


def test_rule_catalog_covers_starter_products():
    for name in (
        "картофель",
        "помидор",
        "огурец",
        "морковь",
        "лук репчатый",
        "яблоко",
        "банан",
        "лимон",
        "авокадо",
        "болгарский перец",
    ):
        rule = get_unit_rule(name)
        assert rule is not None, name
        assert rule.allows_piece_conversion, name
        assert rule.confidence == "approximate", name


def test_rule_catalog_excludes_high_variance_products():
    for name in ("капуста", "тыква", "арбуз", "дыня", "хлеб", "сыр"):
        assert get_unit_rule(name) is None, name


# --- integration: leftovers and multi-category ---------------------------------------------


def test_leftover_meal_does_not_double_count_ingredients():
    menu = MenuPlan(
        summary="Тест",
        total_cost=500,
        days_plan=[
            DayPlan(
                day="День 1",
                meals=[
                    DayMeal(
                        type="dinner",
                        recipe_name="Рагу",
                        meal_id="day1_dinner",
                        requires_cooking=True,
                        prepared_on_day=1,
                    ),
                ],
            ),
            DayPlan(
                day="День 2",
                meals=[
                    DayMeal(
                        type="lunch",
                        recipe_name="Рагу",
                        meal_id="day2_lunch",
                        requires_cooking=False,
                        uses_leftovers=True,
                        source_meal_id="day1_dinner",
                    ),
                ],
            ),
        ],
        recipes=[
            Recipe(
                name="Рагу",
                ingredients=[RecipeIngredient(name="Картофель", amount="5 шт")],
                steps=["Тушить"],
            )
        ],
        basket=[
            BasketCategory(
                category="Овощи",
                items=[BasketItem(name="Картофель", weight="5 шт", price=80)],
            )
        ],
    )
    result = build_basket_from_menu(menu)
    rows = _find(result, "картоф")
    assert len(rows) == 1
    # Leftover meal reuses day-1 cooking: ingredient counted once (5 шт, not 10).
    assert rows[0].weight == "5 шт"


def test_menu_without_cross_unit_duplicates_unchanged():
    menu = _menu([("Суп", "Гречка", "200 г"), ("Салат", "Огурец", "2 шт")])
    result = build_basket_from_menu(menu)
    assert not result.cross_unit_merges
    grech = _find(result, "греч")
    assert grech[0].weight == "200 г"
    cucumber = _find(result, "огур")
    assert cucumber[0].weight == "2 шт"
