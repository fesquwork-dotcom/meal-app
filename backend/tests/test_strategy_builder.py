from datetime import datetime, timezone

import pytest

from strategy import StrategyBuilder, StrategyValidationError, validate_strategy_for_request
from strategy.context import ProfileContext
from strategy.models import WeeklyStrategy


def _full_profile() -> dict[str, object]:
    return {
        "goal": "healthy",
        "days": 7,
        "budget": 4500.0,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "meals_per_day": 3,
        "proteins": ["chicken", "fish"],
        "cooktime": "fast",
        "allergies": "орехи, лактоза",
    }


def _strategy_from_profile(profile: dict[str, object]) -> WeeklyStrategy:
    return StrategyBuilder(clock=lambda: datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)).build(
        profile
    )


def test_builder_returns_fully_populated_strategy():
    fixed_now = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    builder = StrategyBuilder(clock=lambda: fixed_now)

    strategy = builder.build(_full_profile())

    assert strategy.strategy_version == 5
    assert strategy.goal == "healthy"
    assert strategy.days == 7
    assert strategy.budget == 4500.0
    assert strategy.meal_types == ["breakfast", "lunch", "dinner"]
    assert strategy.meals_per_day == 3
    assert strategy.cook_days == [1, 2, 3, 4, 5, 6, 7]
    assert strategy.shopping_days == [1]
    assert strategy.leftovers_enabled is True
    assert strategy.repeat_breakfasts is False
    assert strategy.repeat_lunches is False
    assert strategy.repeat_dinners is False
    assert strategy.preferred_proteins == ["chicken", "fish"]
    assert set(strategy.excluded_products) == {"орехи", "лактоза"}
    assert strategy.cooking_time_limit == 20
    assert strategy.generated_at == "2026-03-10T12:00:00+00:00"


def test_builder_uses_defaults_for_missing_fields():
    builder = StrategyBuilder(clock=lambda: datetime(2026, 1, 1, tzinfo=timezone.utc))

    strategy = builder.build({})

    assert strategy.goal == "home"
    assert strategy.days == 5
    assert strategy.budget == 3000.0
    assert strategy.meal_types == ["breakfast", "lunch", "dinner"]
    assert strategy.meals_per_day == 3
    assert strategy.preferred_proteins == ["any"]
    assert strategy.excluded_products == []
    assert strategy.cooking_time_limit == 45
    assert strategy.generated_at.endswith("+00:00")


def test_builder_derives_meals_per_day_from_meal_types():
    builder = StrategyBuilder()

    strategy = builder.build(
        {
            "meal_types": ["breakfast", "dinner"],
            "meals_per_day": 99,
        }
    )

    assert strategy.meal_types == ["breakfast", "dinner"]
    assert strategy.meals_per_day == 2


def test_five_day_plan_does_not_create_day_six_or_seven():
    builder = StrategyBuilder()

    strategy = builder.build({"days": 5, "goal": "budget", "cooktime": "medium"})

    assert strategy.days == 5
    assert all(1 <= day <= 5 for day in strategy.cook_days)
    assert all(1 <= day <= 5 for day in strategy.shopping_days)
    assert 6 not in strategy.cook_days
    assert 7 not in strategy.cook_days


def test_seven_day_plan_allows_day_seven():
    builder = StrategyBuilder()

    strategy = builder.build({"days": 7, "goal": "budget", "cooktime": "medium"})

    assert 7 in strategy.cook_days


def test_builder_budget_goal_enables_repeats_and_split_shopping():
    builder = StrategyBuilder()

    strategy = builder.build(
        {
            "goal": "budget",
            "days": 7,
            "cooktime": "medium",
        }
    )

    assert strategy.repeat_breakfasts is True
    assert strategy.repeat_lunches is True
    assert strategy.repeat_dinners is True
    assert strategy.shopping_days == [1, 4]
    assert strategy.cook_days == [1, 3, 5, 7]


def test_builder_treats_allergies_none_as_empty_exclusions():
    builder = StrategyBuilder()

    strategy = builder.build({"allergies": "нет"})

    assert strategy.excluded_products == []


def test_same_profile_builds_same_strategy_except_generated_at():
    profile = _full_profile()
    fixed_now = datetime(2026, 3, 10, 12, 0, tzinfo=timezone.utc)
    builder = StrategyBuilder(clock=lambda: fixed_now)

    first = builder.build(profile)
    second = builder.build(profile)

    assert first.model_dump(exclude={"generated_at"}) == second.model_dump(exclude={"generated_at"})
    assert first.generated_at == second.generated_at


def test_profile_context_normalizes_invalid_values():
    context = ProfileContext.from_profile(
        {
            "goal": "unknown",
            "days": 99,
            "budget": -10,
            "proteins": ["chicken", "invalid", "chicken"],
            "cooktime": "unknown",
            "allergies": 123,
        }
    )

    assert context.goal == "home"
    assert context.days == 7
    assert context.budget == 500.0
    assert context.proteins == ["chicken"]
    assert context.cooktime == "medium"
    assert context.allergies == "нет"


def test_profile_context_clamps_legacy_upper_limits():
    context = ProfileContext.from_profile({"days": 14, "budget": 80_000})
    assert context.days == 7
    assert context.budget == 50_000.0


def test_profile_context_merges_legacy_intolerance_into_allergies_without_duplicates():
    context = ProfileContext.from_profile(
        {
            "allergies": "молоко, арахис",
            "dietary_constraints": [
                {
                    "id": "dc_000000000001",
                    "kind": "intolerance",
                    "value": "Молоко",
                    "canonical_value": "молоко",
                },
                {
                    "id": "dc_000000000002",
                    "kind": "intolerance",
                    "value": "глютен",
                    "canonical_value": "глютен",
                },
            ],
        }
    )
    assert context.allergies == "молоко, арахис, глютен"


def test_intolerance_projection_preserves_decision_exclusions():
    legacy = _strategy_from_profile(
        {
            **_full_profile(),
            "allergies": "нет",
            "dietary_constraints": [
                {
                    "id": "dc_000000000001",
                    "kind": "intolerance",
                    "value": "молоко",
                    "canonical_value": "молоко",
                }
            ],
        }
    )
    projected = _strategy_from_profile(
        {
            **_full_profile(),
            "allergies": "молоко",
            "dietary_constraints": [],
        }
    )
    assert legacy.excluded_products == projected.excluded_products


def test_validate_strategy_for_request_accepts_matching_contract():
    strategy = _strategy_from_profile(_full_profile())

    validate_strategy_for_request(
        strategy,
        days=7,
        budget=4500.0,
        meal_types=["breakfast", "lunch", "dinner"],
        meals_per_day=3,
        goal="healthy",
        proteins=["chicken", "fish"],
        allergies="орехи, лактоза",
    )


def test_validate_strategy_for_request_detects_days_conflict():
    strategy = _strategy_from_profile({"days": 5})

    with pytest.raises(StrategyValidationError) as exc_info:
        validate_strategy_for_request(
            strategy,
            days=7,
            budget=strategy.budget,
            meal_types=strategy.meal_types,
            meals_per_day=strategy.meals_per_day,
            goal=strategy.goal,
            proteins=strategy.preferred_proteins,
            allergies="нет",
        )

    assert exc_info.value.code == "STRATEGY_DAYS_MISMATCH"


def test_validate_strategy_for_request_detects_meal_types_conflict():
    strategy = _strategy_from_profile(_full_profile())

    with pytest.raises(StrategyValidationError) as exc_info:
        validate_strategy_for_request(
            strategy,
            days=7,
            budget=4500.0,
            meal_types=["breakfast", "dinner"],
            meals_per_day=2,
            goal="healthy",
            proteins=["chicken", "fish"],
            allergies="орехи, лактоза",
        )

    assert exc_info.value.code == "STRATEGY_MEAL_TYPES_MISMATCH"


def test_validate_strategy_for_request_detects_goal_conflict():
    strategy = _strategy_from_profile(_full_profile())

    with pytest.raises(StrategyValidationError) as exc_info:
        validate_strategy_for_request(
            strategy,
            days=7,
            budget=4500.0,
            meal_types=["breakfast", "lunch", "dinner"],
            meals_per_day=3,
            goal="budget",
            proteins=["chicken", "fish"],
            allergies="орехи, лактоза",
        )

    assert exc_info.value.code == "STRATEGY_GOAL_MISMATCH"
