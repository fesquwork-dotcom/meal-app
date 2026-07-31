from decimal import Decimal

from menu_models import BasketCategory, BasketItem, DayMeal, DayPlan, MenuPlan, Recipe, RecipeIngredient
from shopping.basket_builder import build_basket_from_menu


def _menu_with_recipes() -> MenuPlan:
    return MenuPlan(
        summary="Тест",
        total_cost=1000,
        days_plan=[
            DayPlan(
                day="День 1",
                meals=[
                    DayMeal(
                        type="dinner",
                        recipe_name="Курица",
                        meal_id="day1_dinner",
                        requires_cooking=True,
                        prepared_on_day=1,
                    ),
                    DayMeal(
                        type="lunch",
                        recipe_name="Салат",
                        meal_id="day2_lunch",
                        requires_cooking=False,
                        uses_leftovers=True,
                        source_meal_id="day1_dinner",
                    ),
                ],
            )
        ],
        recipes=[
            Recipe(
                name="Курица",
                ingredients=[
                    RecipeIngredient(name="Куриная грудка", amount="500 г"),
                    RecipeIngredient(name="Картофель", amount="300 г"),
                ],
                steps=["Готовить"],
            ),
            Recipe(
                name="Салат",
                ingredients=[RecipeIngredient(name="Огурец", amount="1 шт")],
                steps=["Смешать"],
            ),
        ],
        basket=[
            BasketCategory(
                category="Мясо",
                items=[BasketItem(name="Куриная грудка", weight="500 г", price=350)],
            ),
            BasketCategory(
                category="Овощи",
                items=[
                    BasketItem(name="Картофель", weight="300 г", price=80),
                    BasketItem(name="Огурец", weight="1 шт", price=40),
                ],
            ),
        ],
    )


def test_build_basket_from_recipes_excludes_leftover_meal():
    menu = _menu_with_recipes()
    result = build_basket_from_menu(menu)

    names = [item.name.lower() for category in result.basket for item in category.items]
    assert any("курин" in name for name in names)
    assert any("картоф" in name for name in names)
    assert not any("огурец" in name for name in names)


def test_shared_ingredient_merge():
    menu = _menu_with_recipes()
    menu.days_plan[0].meals.append(
        DayMeal(
            type="breakfast",
            recipe_name="Каша",
            meal_id="day1_breakfast",
            requires_cooking=True,
            prepared_on_day=1,
        )
    )
    menu.recipes.append(
        Recipe(
            name="Каша",
            ingredients=[RecipeIngredient(name="Молоко", amount="200 мл")],
            steps=["Варить"],
        )
    )
    menu.recipes[0].ingredients.append(RecipeIngredient(name="Молоко", amount="100 мл"))

    result = build_basket_from_menu(menu)
    milk_lines = [
        item
        for category in result.basket
        for item in category.items
        if "молок" in item.name.lower()
    ]
    assert len(milk_lines) == 1
    assert result.merged_duplicate_count >= 1


def test_deterministic_repeated_build():
    menu = _menu_with_recipes()
    first = build_basket_from_menu(menu)
    second = build_basket_from_menu(menu)
    assert first.total_cost == second.total_cost
    assert first.basket[0].category == second.basket[0].category
    assert first.basket[0].items[0].name == second.basket[0].items[0].name


def test_total_cost_from_basket_lines():
    menu = _menu_with_recipes()
    result = build_basket_from_menu(menu)
    assert result.total_cost == Decimal("430.00")


# --- Sprint 10.5.1: scientific notation must never reach the basket ----------------


def _assert_no_unsafe_text(basket) -> None:
    for category in basket:
        assert "E+" not in category.category and "E-" not in category.category
        for item in category.items:
            for value in (item.name, item.weight, *item.shopping_advice, *item.badges):
                assert "E+" not in value, value
                assert "E-" not in value, value
                assert "NaN" not in value, value
                assert "Infinity" not in value, value


def test_round_merged_weight_formats_without_exponent():
    menu = _menu_with_recipes()
    # 400 g + 800 g of the same product = 1200 g (Decimal.normalize() → 1.2E+3 regression).
    menu.days_plan[0].meals.append(
        DayMeal(
            type="breakfast",
            recipe_name="Рагу",
            meal_id="day1_breakfast",
            requires_cooking=True,
            prepared_on_day=1,
        )
    )
    menu.recipes.append(
        Recipe(
            name="Рагу",
            ingredients=[RecipeIngredient(name="Кабачок", amount="800 г")],
            steps=["Тушить"],
        )
    )
    menu.recipes[0].ingredients.append(RecipeIngredient(name="Кабачок", amount="400 г"))

    result = build_basket_from_menu(menu)

    zucchini = [
        item
        for category in result.basket
        for item in category.items
        if "кабач" in item.name.lower()
    ]
    assert len(zucchini) == 1
    # Sprint 10.5.2 display rules: >=1000 g renders as kg.
    assert zucchini[0].weight == "1.2 кг"
    _assert_no_unsafe_text(result.basket)


def test_basket_guard_rewrites_unsafe_text(caplog):
    """Injected exponent text is caught by the guard, logged, and rewritten."""
    import logging

    from shopping.basket_builder import _sanitize_basket_text

    basket = [
        BasketCategory(
            category="Овощи",
            items=[BasketItem(name="Кабачок", weight="1.2E+3 г", price=100.0)],
        )
    ]
    with caplog.at_level(logging.ERROR):
        sanitized = _sanitize_basket_text(basket)

    assert sanitized[0].items[0].weight == "1200 г"
    assert any("basket_text_unsafe" in record.getMessage() for record in caplog.records)


def test_basket_guard_keeps_safe_text_unchanged(caplog):
    import logging

    from shopping.basket_builder import _sanitize_basket_text

    basket = [
        BasketCategory(
            category="Овощи",
            items=[BasketItem(name="Кабачок", weight="1200 г", price=100.0)],
        )
    ]
    with caplog.at_level(logging.ERROR):
        sanitized = _sanitize_basket_text(basket)

    assert sanitized[0].items[0] == basket[0].items[0]
    assert not [r for r in caplog.records if "basket_text_unsafe" in r.getMessage()]
