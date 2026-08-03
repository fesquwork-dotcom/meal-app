"""Sprint 10.7 — deterministic cooking/leftover metadata normalization."""

from __future__ import annotations

from cooking_identity import validate_cooking_instance_graph
from menu_metadata_normalize import normalize_cooking_leftover_metadata
from menu_models import (
    BasketCategory,
    BasketItem,
    DayMeal,
    DayPlan,
    MenuPlan,
    Recipe,
    RecipeIngredient,
)
from recipe_identity import validate_ingredient_contributions


def _batch_menu(*, leftover_instance: str = "wrong_instance") -> MenuPlan:
    return MenuPlan(
        summary="Тест",
        total_cost=500,
        days_plan=[
            DayPlan(
                day="День 1",
                meals=[
                    DayMeal(
                        type="dinner",
                        recipe_name="Запечённая курица",
                        recipe_id="recipe_roast_chicken",
                        cooking_instance_id="batch_chicken_day1",
                        meal_id="day1_dinner",
                        requires_cooking=True,
                        prepared_on_day=1,
                    )
                ],
            ),
            DayPlan(
                day="День 2",
                meals=[
                    DayMeal(
                        type="lunch",
                        recipe_name="Боул с курицей",
                        recipe_id="recipe_chicken_bowl",
                        cooking_instance_id=leftover_instance,
                        meal_id="day2_lunch",
                        uses_leftovers=True,
                        source_meal_id="day1_dinner",
                        prepared_on_day=9,
                    )
                ],
            ),
        ],
        recipes=[
            Recipe(
                name="Запечённая курица",
                recipe_id="recipe_roast_chicken",
                ingredients=[
                    RecipeIngredient(name="Курица", amount="500 г", contribution="purchase"),
                ],
                steps=["Запечь"],
            ),
            Recipe(
                name="Боул с курицей",
                recipe_id="recipe_chicken_bowl",
                ingredients=[
                    RecipeIngredient(name="Курица", amount="200 г", contribution="purchase"),
                    RecipeIngredient(name="Огурец", amount="1 шт", contribution="purchase"),
                ],
                steps=["Собрать"],
            ),
        ],
        basket=[
            BasketCategory(
                category="Продукты",
                items=[
                    BasketItem(name="Курица", weight="500 г", price=300),
                    BasketItem(name="Огурец", weight="1 шт", price=40),
                ],
            )
        ],
    )


def test_unambiguous_cooking_instance_mismatch_normalized():
    menu = _batch_menu(leftover_instance="wrong_instance")
    updated, stats = normalize_cooking_leftover_metadata(menu, request_id="req")
    assert stats.cooking_normalized >= 1
    leftover = updated.days_plan[1].meals[0]
    assert leftover.cooking_instance_id == "batch_chicken_day1"
    assert not any(
        i.code == "COOKING_INSTANCE_SOURCE_MISMATCH"
        for i in validate_cooking_instance_graph(updated, strategy_aware=True)
    )


def test_unambiguous_prepared_on_day_normalized():
    menu = _batch_menu()
    # Cooking meal with wrong prepared day.
    menu.days_plan[0].meals[0] = menu.days_plan[0].meals[0].model_copy(
        update={"prepared_on_day": 3}
    )
    updated, stats = normalize_cooking_leftover_metadata(menu, request_id="req")
    assert stats.cooking_normalized >= 1
    assert updated.days_plan[0].meals[0].prepared_on_day == 1
    leftover = updated.days_plan[1].meals[0]
    assert leftover.prepared_on_day == 1


def test_missing_source_cannot_normalize_instance():
    menu = _batch_menu()
    menu.days_plan[1].meals[0] = menu.days_plan[1].meals[0].model_copy(
        update={"source_meal_id": "missing", "cooking_instance_id": "x"}
    )
    updated, stats = normalize_cooking_leftover_metadata(menu, request_id="req")
    assert stats.cooking_ambiguous >= 1
    assert updated.days_plan[1].meals[0].cooking_instance_id == "x"
    issues = validate_cooking_instance_graph(updated, strategy_aware=True)
    assert any(i.code == "COOKING_INSTANCE_SOURCE_MISMATCH" for i in issues)


def test_source_on_same_or_future_day_remains_invalid():
    menu = _batch_menu()
    # Point leftover at a meal on the same day (create sibling).
    menu.days_plan[1].meals.append(
        DayMeal(
            type="dinner",
            recipe_name="Салат",
            recipe_id="recipe_salad",
            cooking_instance_id="cook_salad",
            meal_id="day2_dinner",
            requires_cooking=True,
            prepared_on_day=2,
        )
    )
    menu.recipes.append(
        Recipe(
            name="Салат",
            recipe_id="recipe_salad",
            ingredients=[RecipeIngredient(name="Листья", amount="100 г", contribution="purchase")],
            steps=["Смешать"],
        )
    )
    menu.days_plan[1].meals[0] = menu.days_plan[1].meals[0].model_copy(
        update={"source_meal_id": "day2_dinner", "cooking_instance_id": "cook_salad"}
    )
    updated, stats = normalize_cooking_leftover_metadata(menu, request_id="req")
    assert stats.cooking_ambiguous >= 1
    issues = validate_cooking_instance_graph(updated, strategy_aware=True)
    assert any(i.code == "COOKING_INSTANCE_SOURCE_MISMATCH" for i in issues)


def test_leftover_ingredient_linkage_normalizes():
    menu = _batch_menu()
    updated, stats = normalize_cooking_leftover_metadata(menu, request_id="req")
    assert stats.leftover_normalized == 1
    bowl = next(r for r in updated.recipes if r.recipe_id == "recipe_chicken_bowl")
    chicken = next(i for i in bowl.ingredients if i.name == "Курица")
    cucumber = next(i for i in bowl.ingredients if i.name == "Огурец")
    assert chicken.contribution == "from_source"
    assert chicken.amount == "200 г"  # amount preserved
    assert cucumber.contribution == "purchase"
    issues = validate_ingredient_contributions(updated, strategy_aware=True)
    assert not any(i.code == "LEFTOVER_SOURCE_INGREDIENT_MISSING" for i in issues)


def test_ambiguous_ingredient_relation_remains_failure():
    menu = _batch_menu()
    # Rename leftover ingredients so nothing matches source.
    menu.recipes[1] = menu.recipes[1].model_copy(
        update={
            "ingredients": [
                RecipeIngredient(name="Тофу", amount="200 г", contribution="purchase"),
            ]
        }
    )
    updated, stats = normalize_cooking_leftover_metadata(menu, request_id="req")
    assert stats.leftover_ambiguous >= 1
    issues = validate_ingredient_contributions(updated, strategy_aware=True)
    assert any(i.code == "LEFTOVER_SOURCE_INGREDIENT_MISSING" for i in issues)


def test_unrelated_meal_metadata_unchanged():
    menu = _batch_menu()
    menu.days_plan[0].meals.append(
        DayMeal(
            type="breakfast",
            recipe_name="Овсянка",
            recipe_id="recipe_oats",
            cooking_instance_id="cook_oats",
            meal_id="day1_breakfast",
            requires_cooking=True,
            prepared_on_day=1,
        )
    )
    menu.recipes.append(
        Recipe(
            name="Овсянка",
            recipe_id="recipe_oats",
            ingredients=[RecipeIngredient(name="Овсянка", amount="80 г", contribution="purchase")],
            steps=["Варить"],
        )
    )
    before = menu.days_plan[0].meals[1].model_copy(deep=True)
    updated, _ = normalize_cooking_leftover_metadata(menu, request_id="req")
    after = next(m for m in updated.days_plan[0].meals if m.meal_id == "day1_breakfast")
    assert after.cooking_instance_id == before.cooking_instance_id
    assert after.prepared_on_day == before.prepared_on_day
    assert after.requires_cooking == before.requires_cooking


def test_normalization_then_strict_validation_passes():
    menu = _batch_menu(leftover_instance="totally_wrong")
    updated, _ = normalize_cooking_leftover_metadata(menu, request_id="req")
    cooking = validate_cooking_instance_graph(updated, strategy_aware=True)
    contrib = validate_ingredient_contributions(updated, strategy_aware=True)
    assert not cooking
    assert not any(i.code == "LEFTOVER_SOURCE_INGREDIENT_MISSING" for i in contrib)
