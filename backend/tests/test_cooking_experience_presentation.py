"""Presentation-layer tests for display names, glossary, tips, substitutes, basket advice."""

from menu_models import BasketItem, IngredientSubstitute, Recipe, RecipeIngredient
from shopping.basket_builder import DEFAULT_CATEGORY, _guess_category, build_basket_from_menu
from shopping.display_names import glossary_note, resolve_display_name
from shopping.normalization import display_ingredient_name, ingredient_glossary_note
from shopping.shopping_advice import purchase_badges, shopping_advice_for
from menu_models import BasketCategory, DayMeal, DayPlan, MenuPlan


def test_canonical_alias_becomes_common_display_name():
    assert resolve_display_name("томат") == "Помидоры"
    assert display_ingredient_name("Томаты свежие") == "Помидоры"
    assert display_ingredient_name("куриная грудка") == "Куриное филе"


def test_legacy_display_name_capitalizes_unknown():
    assert display_ingredient_name("экзотический фрукт") == "Экзотический фрукт"


def test_soft_match_does_not_false_positive_on_substrings():
    assert resolve_display_name("булгур") == "Булгур"
    assert resolve_display_name("Томаты свежие") == "Помидоры"


def test_glossary_for_rare_ingredients():
    assert glossary_note("Тахини") == "кунжутная паста"
    assert ingredient_glossary_note("булгур") == "пшеничная крупа"
    assert glossary_note("Киноа") == "зерновая культура"
    assert glossary_note("Нут") == "турецкий горох"
    assert glossary_note("Рис") is None


def test_recipe_tips_and_substitutes_optional():
    recipe = Recipe(
        name="Плов",
        ingredients=[RecipeIngredient(name="Рис", amount="300 г")],
        steps=["Варить"],
        tips=["Оставьте под крышкой ещё 5 минут."],
        substitutes=[IngredientSubstitute(original="Авокадо", replacement="Огурцом")],
    )
    assert recipe.tips == ["Оставьте под крышкой ещё 5 минут."]
    assert recipe.substitutes[0].original == "Авокадо"

    empty = Recipe(
        name="Каша",
        ingredients=[RecipeIngredient(name="Овсянка", amount="50 г")],
        steps=["Варить"],
    )
    assert empty.tips == []
    assert empty.substitutes == []


def test_recipe_accepts_legacy_substitute_keys():
    recipe = Recipe.model_validate(
        {
            "name": "Салат",
            "ingredients": [{"name": "Авокадо", "amount": "1 шт"}],
            "steps": ["Нарезать"],
            "substitutes": [{"from": "Авокадо", "to": "Огурец"}],
            "tips": "Добавьте лимонный сок",
        }
    )
    assert recipe.tips == ["Добавьте лимонный сок"]
    assert recipe.substitutes[0].replacement == "Огурец"


def test_shopping_advice_types():
    chilled = shopping_advice_for("Куриное филе", "Мясо")
    assert "Лучше купить охлаждённым" in chilled

    bulk = shopping_advice_for("Рис", "Крупы")
    assert "Можно взять большую упаковку" in bulk

    specialty = shopping_advice_for("Тахини", "Соусы")
    assert "Проще найти в крупных супермаркетах" in specialty

    fresh = shopping_advice_for("Укроп", "Овощи")
    assert "Нужно купить свежим" in fresh
    assert "Купить заранее" in fresh


def test_purchase_badges():
    badges = purchase_badges(
        used_in_recipes=3,
        shopping_advice=["Нужно купить свежим"],
    )
    assert "Используется в 3 блюдах" in badges
    assert "Нужно купить свежим" in badges

    once = purchase_badges(used_in_recipes=1, shopping_advice=[])
    assert once == ["Покупается один раз"]


def test_unknown_category_is_prochee():
    assert _guess_category("Неизвестный продукт xyz", {}) == DEFAULT_CATEGORY


def test_basket_rebuild_uses_display_name_and_pantry_excluded():
    menu = MenuPlan(
        summary="Тест",
        total_cost=100,
        days_plan=[
            DayPlan(
                day="День 1",
                meals=[
                    DayMeal(
                        type="dinner",
                        recipe_name="Блюдо",
                        meal_id="day1_dinner",
                        requires_cooking=True,
                        prepared_on_day=1,
                    )
                ],
            )
        ],
        recipes=[
            Recipe(
                name="Блюдо",
                ingredients=[
                    RecipeIngredient(name="Томаты", amount="200 г"),
                    RecipeIngredient(name="Соль", amount="по вкусу", contribution="pantry"),
                    RecipeIngredient(name="Рис", amount="150 г"),
                ],
                steps=["Готовить"],
            )
        ],
        basket=[
            BasketCategory(
                category="Овощи",
                items=[BasketItem(name="Томаты", weight="200 г", price=50)],
            ),
            BasketCategory(
                category="Крупы",
                items=[BasketItem(name="Рис", weight="150 г", price=40)],
            ),
        ],
    )

    result = build_basket_from_menu(menu)
    names = [item.name for category in result.basket for item in category.items]
    assert "Помидоры" in names
    assert "Рис" in names
    assert not any("соль" in name.lower() for name in names)

    tomato = next(item for category in result.basket for item in category.items if item.name == "Помидоры")
    assert tomato.used_in_recipes == 1
    assert tomato.shopping_advice
    assert tomato.badges
