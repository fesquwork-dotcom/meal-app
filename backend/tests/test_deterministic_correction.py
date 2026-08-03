"""Sprint 10.3.2: deterministic total_cost, targeted constraint correction,
retry regression guard, duplicate/cooktime diagnostics."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date

import pytest

import claude_service
import config
from claude_exceptions import MenuConstraintError
from menu_models import MenuPlan
from menu_validation import (
    MenuValidationRequest,
    compute_basket_total,
    normalize_total_cost,
    validate_menu_plan,
)
from strategy.prompt import build_targeted_correction_prompt
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict, clone_menu
from tests.strategy_fixtures import build_test_profile, build_test_strategy


def _request(**overrides) -> MenuValidationRequest:
    base = {
        "days": 3,
        "budget": 3000.0,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "meals_per_day": 3,
        "persons": 2,
        "cooktime": "medium",
        "allergies": "нет",
    }
    base.update(overrides)
    return MenuValidationRequest(**base)


# --- 1. Deterministic total_cost -------------------------------------------------


def test_arithmetic_only_mismatch_is_normalized():
    menu = build_valid_menu_dict(days=3)
    menu["total_cost"] = 9999.0
    plan = MenuPlan.model_validate(menu)

    normalized_plan, info = normalize_total_cost(plan)

    assert info.normalized is True
    basket_sum = float(compute_basket_total(plan))
    assert normalized_plan.total_cost == basket_sum
    assert info.model_total == 9999.0
    assert info.calculated_total == basket_sum
    assert info.difference == round(abs(9999.0 - basket_sum), 2)
    # Individual price estimates are untouched.
    assert [item.price for cat in normalized_plan.basket for item in cat.items] == [
        item.price for cat in plan.basket for item in cat.items
    ]


def test_consistent_total_cost_is_not_rewritten():
    menu = build_valid_menu_dict(days=3)
    plan = MenuPlan.model_validate(menu)
    plan = plan.model_copy(update={"total_cost": float(compute_basket_total(plan))})

    same_plan, info = normalize_total_cost(plan)

    assert info.normalized is False
    assert info.reason == "already_consistent"
    assert same_plan.total_cost == plan.total_cost


def test_invalid_price_contribution_is_not_masked():
    menu = build_valid_menu_dict(days=3)
    plan = MenuPlan.model_validate(menu)
    plan.basket[0].items[0].price = float("nan")

    unchanged_plan, info = normalize_total_cost(plan)

    assert info.normalized is False
    assert info.reason == "invalid_price_contributions"
    assert info.calculated_total is None
    assert unchanged_plan.total_cost == plan.total_cost


def test_money_rounding_is_half_up_to_kopecks():
    menu = build_valid_menu_dict(days=3)
    plan = MenuPlan.model_validate(menu)
    plan.basket[0].items[0].price = 10.005
    plan.basket[0].items[1].price = 20.0
    for item in plan.basket[0].items[2:]:
        item.price = 0.0

    total = compute_basket_total(plan)
    assert float(total) == 30.01


def test_normalized_plan_passes_total_cost_validation():
    menu = build_valid_menu_dict(days=3)
    menu["total_cost"] = 9999.0
    plan = MenuPlan.model_validate(menu)
    plan, _info = normalize_total_cost(plan)

    result = validate_menu_plan(plan, _request())
    assert not any(issue.code == "TOTAL_COST_MISMATCH" for issue in result.errors)


# --- 5/6. Duplicate and cooktime diagnostics --------------------------------------


def _with_meal_ids(menu: dict) -> dict:
    for day_index, day in enumerate(menu["days_plan"]):
        for meal in day["meals"]:
            meal["meal_id"] = f"day{day_index + 1}_{meal['type']}"
    return menu


def test_duplicate_excessive_has_structured_diagnostics():
    menu = _with_meal_ids(clone_menu(build_valid_menu_dict(days=3)))
    repeated = menu["days_plan"][0]["meals"][0]["recipe_name"]
    menu["days_plan"][1]["meals"][0]["recipe_name"] = repeated
    menu["days_plan"][2]["meals"][0]["recipe_name"] = repeated

    result = validate_menu_plan(MenuPlan.model_validate(menu), _request())

    issue = next(i for i in result.errors if i.code == "MEAL_DUPLICATE_EXCESSIVE")
    meta = issue.meta
    assert meta is not None
    assert meta["meal_name"] == repeated
    assert meta["independent_count"] == 3
    assert meta["allowed_count"] == 2
    assert meta["replacements_needed"] == 1
    assert meta["day_numbers"] == [1, 2, 3]
    assert meta["meal_ids"] == ["day1_breakfast", "day2_breakfast", "day3_breakfast"]
    assert meta["meal_types"] == ["breakfast"]
    assert len(meta["independent_positions"]) == 3


def test_linked_leftovers_are_not_excessive_duplicates():
    menu = _with_meal_ids(clone_menu(build_valid_menu_dict(days=3)))
    repeated = menu["days_plan"][0]["meals"][0]["recipe_name"]
    for day_index in (1, 2):
        meal = menu["days_plan"][day_index]["meals"][0]
        meal["recipe_name"] = repeated
        meal["uses_leftovers"] = True
        meal["source_meal_id"] = "day1_breakfast"

    result = validate_menu_plan(MenuPlan.model_validate(menu), _request())

    assert not any(issue.code == "MEAL_DUPLICATE_EXCESSIVE" for issue in result.errors)
    assert not any(issue.code == "MEAL_DUPLICATE_WARNING" for issue in result.warnings)


def test_dangling_leftover_link_still_counts_as_duplicate():
    menu = _with_meal_ids(clone_menu(build_valid_menu_dict(days=3)))
    repeated = menu["days_plan"][0]["meals"][0]["recipe_name"]
    for day_index in (1, 2):
        meal = menu["days_plan"][day_index]["meals"][0]
        meal["recipe_name"] = repeated
        meal["uses_leftovers"] = True
        meal["source_meal_id"] = "nonexistent_meal"

    result = validate_menu_plan(MenuPlan.model_validate(menu), _request())

    assert any(issue.code == "MEAL_DUPLICATE_EXCESSIVE" for issue in result.errors)


def test_cooktime_exceeded_has_diagnostics_and_no_clamp():
    menu = _with_meal_ids(clone_menu(build_valid_menu_dict(days=1)))
    menu["recipes"][0]["cook_time"] = "60 минут"
    plan = MenuPlan.model_validate(menu)

    result = validate_menu_plan(plan, _request(days=1, cooktime="fast"))

    issue = next(i for i in result.errors if i.code == "COOKTIME_EXCEEDED")
    meta = issue.meta
    assert meta is not None
    assert meta["recipe_title"] == menu["recipes"][0]["name"]
    assert meta["actual_minutes"] == 60
    assert meta["allowed_minutes"] == 20
    assert meta["meal_ids"]
    # The validator never rewrites cook_time (no auto-clamp).
    assert plan.recipes[0].cook_time == "60 минут"


# --- 2/3. Targeted correction prompt ----------------------------------------------


def test_targeted_prompt_cooking_leftover_structural_feedback():
    strategy = build_test_strategy(days=3)
    prompt = build_targeted_correction_prompt(
        [
            {
                "code": "COOKING_INSTANCE_SOURCE_MISMATCH",
                "message": "instance mismatch",
                "meta": {
                    "meal_id": "day2_lunch",
                    "source_meal_id": "day1_dinner",
                    "expected_cooking_instance_id": "batch_1",
                    "field": "cooking_instance_id",
                },
            },
            {
                "code": "LEFTOVER_SOURCE_INGREDIENT_MISSING",
                "message": "need from_source",
                "meta": {
                    "meal_id": "day2_lunch",
                    "source_meal_id": "day1_dinner",
                    "field": "ingredient.contribution",
                },
            },
        ],
        strategy,
    )
    assert "day2_lunch" in prompt
    assert "day1_dinner" in prompt
    assert "batch_1" in prompt
    assert "from_source" in prompt
    assert "НЕ переписывай всё меню заново" in prompt


def test_targeted_prompt_cooktime_names_exact_recipe():
    strategy = build_test_strategy(days=3, cooktime="fast")
    prompt = build_targeted_correction_prompt(
        [
            {
                "code": "COOKTIME_EXCEEDED",
                "message": "cook_time exceeds",
                "meta": {
                    "recipe_id": "recipe_day2_dinner",
                    "recipe_title": "Плов",
                    "actual_minutes": 35,
                    "allowed_minutes": 20,
                    "meal_ids": ["day2_dinner"],
                },
            }
        ],
        strategy,
    )
    assert "recipe_day2_dinner" in prompt
    assert "cook_time=35" in prompt
    assert "<= 20" in prompt
    assert "day2_dinner" in prompt
    assert "ТОЛЬКО этот рецепт" in prompt
    assert "не просто уменьшай число cook_time" in prompt


def test_targeted_prompt_duplicate_names_positions_and_replacement_count():
    strategy = build_test_strategy(days=3)
    prompt = build_targeted_correction_prompt(
        [
            {
                "code": "MEAL_DUPLICATE_EXCESSIVE",
                "message": "duplicate",
                "meta": {
                    "duplicate_key": "овсяная каша",
                    "meal_name": "Овсяная каша",
                    "independent_count": 4,
                    "allowed_count": 2,
                    "replacements_needed": 2,
                    "independent_positions": [
                        {"day": 1, "meal_type": "breakfast", "meal_id": "day1_breakfast"},
                        {"day": 2, "meal_type": "breakfast", "meal_id": "day2_breakfast"},
                        {"day": 4, "meal_type": "breakfast", "meal_id": "day4_breakfast"},
                        {"day": 6, "meal_type": "breakfast", "meal_id": "day6_breakfast"},
                    ],
                },
            }
        ],
        strategy,
    )
    assert "Овсяная каша" in prompt
    assert "Замени РОВНО 2" in prompt
    assert "день 4, breakfast (day4_breakfast)" in prompt
    assert "Не уменьшай разнообразие" in prompt


def test_targeted_prompt_protects_valid_elements():
    strategy = build_test_strategy(days=3)
    prompt = build_targeted_correction_prompt(
        [{"code": "MEAL_DUPLICATE_EXCESSIVE", "message": "dup", "meta": {}}],
        strategy,
    )
    assert "modify only the items explicitly listed below" in prompt
    assert "сохрани ровно 3 дней и 9 приёмов пищи" in prompt
    assert "НЕ уменьшай количество уникальных рецептов" in prompt
    assert "meal_id, recipe_id и cooking_instance_id" in prompt
    assert "массовое использование leftovers" in prompt
    assert "WEEKLY_STRATEGY" in prompt


def test_targeted_prompt_includes_forbidden_and_once_used_inventory():
    strategy = build_test_strategy(days=3)
    inventory = {
        "allowed_count": 2,
        "used": [
            {"name": "Чечевичный суп с гречкой", "count": 3, "meal_types": ["lunch"]},
            {"name": "Борщ", "count": 1, "meal_types": ["lunch"]},
            {"name": "Овсянка", "count": 2, "meal_types": ["breakfast"]},
        ],
        "at_limit": ["Чечевичный суп с гречкой", "Овсянка"],
        "once_used": ["Борщ"],
        "once_used_by_type": {"lunch": ["Борщ"]},
    }
    prompt = build_targeted_correction_prompt(
        [
            {
                "code": "MEAL_DUPLICATE_EXCESSIVE",
                "message": "dup",
                "meta": {
                    "meal_name": "Чечевичный суп с гречкой",
                    "independent_count": 3,
                    "allowed_count": 2,
                    "replacements_needed": 1,
                    "meal_types": ["lunch"],
                    "independent_positions": [
                        {"day": 1, "meal_type": "lunch", "meal_id": "day1_lunch"},
                        {"day": 2, "meal_type": "lunch", "meal_id": "day2_lunch"},
                        {"day": 7, "meal_type": "lunch", "meal_id": "day7_lunch"},
                    ],
                },
            }
        ],
        strategy,
        meal_inventory=inventory,
    )
    assert "ИНВЕНТАРЬ БЛЮД" in prompt
    assert "ЗАПРЕЩЕНО выбирать как замену" in prompt
    assert "Чечевичный суп с гречкой" in prompt
    assert "Овсянка" in prompt
    assert "Допустимые уникальные блюда" in prompt
    assert "Борщ" in prompt
    assert "НЕ выбирай блюда из запрещённого списка" in prompt


def test_targeted_prompt_continue_from_best_header():
    strategy = build_test_strategy(days=3)
    prompt = build_targeted_correction_prompt(
        [{"code": "MEAL_DUPLICATE_EXCESSIVE", "message": "dup", "meta": {}}],
        strategy,
        strict=True,
        continue_from_best=True,
    )
    assert "база = лучший предыдущий кандидат" in prompt
    assert "ухудшил результат" in prompt


def test_build_meal_usage_inventory_marks_at_limit_and_once_used():
    from menu_validation import build_meal_usage_inventory

    menu = _with_meal_ids(clone_menu(build_valid_menu_dict(days=3)))
    repeated = menu["days_plan"][0]["meals"][0]["recipe_name"]
    menu["days_plan"][1]["meals"][0]["recipe_name"] = repeated
    menu["days_plan"][2]["meals"][0]["recipe_name"] = repeated
    inv = build_meal_usage_inventory(MenuPlan.model_validate(menu))
    assert repeated in inv["at_limit"]
    assert inv["allowed_count"] == 2
    assert any(entry["name"] == repeated and entry["count"] == 3 for entry in inv["used"])


def test_candidate_score_prefers_fewer_issues_over_raw_variety():
    better_fewer_issues = claude_service._candidate_score(
        issue_count=1, unique_recipe_count=11, cooktime_issue_count=0
    )
    worse_more_variety = claude_service._candidate_score(
        issue_count=2, unique_recipe_count=13, cooktime_issue_count=0
    )
    assert better_fewer_issues > worse_more_variety


def test_targeted_prompt_strict_mode_header():
    strategy = build_test_strategy(days=3)
    normal = build_targeted_correction_prompt(
        [{"code": "X", "message": "m", "meta": None}], strategy
    )
    strict = build_targeted_correction_prompt(
        [{"code": "X", "message": "m", "meta": None}], strategy, strict=True
    )
    assert "СТРОГОЕ ИСПРАВЛЕНИЕ" not in normal
    assert "СТРОГОЕ ИСПРАВЛЕНИЕ" in strict
    assert "финальная попытка" in strict


# --- 4/7. Full pipeline: targeted retry, regression guard --------------------------


def _fake_response(payload: dict) -> object:
    from tests.test_anthropic_retry import make_http_response

    return make_http_response(
        200,
        json_body={
            "stop_reason": "end_turn",
            "usage": {"output_tokens": 8000},
            "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}],
        },
    )


def _install_client(monkeypatch, responses: list, prompts: list[str]):
    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **kwargs):
            prompts.append(kwargs["json"]["messages"][0]["content"])
            return responses.pop(0)

    monkeypatch.setattr(claude_service, "create_anthropic_client", lambda: FakeClient())
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")

    async def fake_sleep(_seconds):
        return None

    monkeypatch.setattr(claude_service.asyncio, "sleep", fake_sleep)


def _run(strategy):
    return asyncio.run(
        claude_service.generate_menu(
            budget=strategy.budget,
            days=strategy.days,
            meal_types=list(strategy.meal_types),
            meals_per_day=strategy.meals_per_day,
            persons=2,
            proteins=list(strategy.preferred_proteins),
            goal=strategy.goal,
            cooktime="fast",
            allergies="нет",
            strategy=strategy,
            plan_start_date=date(2026, 7, 18),
            user_id=1,
        )
    )


@pytest.fixture
def strategy():
    from strategy.builder import StrategyBuilder

    return StrategyBuilder().build(build_test_profile(days=3, cooktime="fast"))


def _valid_menu(strategy) -> dict:
    return annotate_cooking_metadata(
        build_valid_menu_dict(days=3, cooktime="15 мин"),
        strategy,
    )


def _menu_with_duplicates(strategy, *, extra_bad: bool = False) -> dict:
    """3 (or 4) independent uses of the day1 breakfast recipe; wrong total_cost."""
    menu = clone_menu(_valid_menu(strategy))
    source = menu["days_plan"][0]["meals"][0]
    for day_index in (1, 2):
        meal = menu["days_plan"][day_index]["meals"][0]
        meal["recipe_name"] = source["recipe_name"]
        meal["recipe_id"] = source["recipe_id"]
    if extra_bad:
        # Fourth duplicate plus a cooktime violation: strictly worse retry.
        lunch = menu["days_plan"][2]["meals"][1]
        lunch["recipe_name"] = source["recipe_name"]
        lunch["recipe_id"] = source["recipe_id"]
        lunch["uses_leftovers"] = False
        lunch["source_meal_id"] = None
        for recipe in menu["recipes"]:
            if recipe["name"] == menu["days_plan"][0]["meals"][1]["recipe_name"]:
                recipe["cook_time"] = "60 мин"
    # Arithmetic-only mismatch: must be normalized away, never sent to Claude.
    menu["total_cost"] = 9999.0
    return menu


def test_targeted_retry_then_success_full_pipeline(monkeypatch, strategy, caplog):
    prompts: list[str] = []
    _install_client(
        monkeypatch,
        [_fake_response(_menu_with_duplicates(strategy)), _fake_response(_valid_menu(strategy))],
        prompts,
    )

    with caplog.at_level(logging.INFO):
        result = _run(strategy)

    assert result["recipes"]
    assert len(prompts) == 2
    # Targeted duplicate instruction with exact positions.
    assert "Замени РОВНО 1" in prompts[1]
    assert "day2_breakfast" in prompts[1]
    assert "modify only the items explicitly listed below" in prompts[1]
    # Deterministic replacement inventory present.
    assert "ИНВЕНТАРЬ БЛЮД" in prompts[1]
    assert "ЗАПРЕЩЕНО выбирать как замену" in prompts[1]
    # Arithmetic-only mismatch was normalized, not delegated to Claude.
    assert "TOTAL_COST_MISMATCH" not in prompts[1]
    assert "total_cost_normalized" in caplog.text
    assert "retry_mode=targeted_constraint" in caplog.text
    assert "constraint_issue_detail" in caplog.text


def test_regression_continues_from_best_candidate_not_worse_retry(
    monkeypatch, strategy, caplog
):
    prompts: list[str] = []
    _install_client(
        monkeypatch,
        [
            _fake_response(_menu_with_duplicates(strategy)),
            _fake_response(_menu_with_duplicates(strategy, extra_bad=True)),
            _fake_response(_valid_menu(strategy)),
        ],
        prompts,
    )

    with caplog.at_level(logging.INFO):
        result = _run(strategy)

    assert result["recipes"]
    assert len(prompts) == 3
    assert "correction_regression_detected" in caplog.text
    assert "continue_from_best=True" in caplog.text
    # Final attempt is strict, but base = best (attempt 1), not the worsened attempt 2.
    assert "СТРОГОЕ ИСПРАВЛЕНИЕ" in prompts[2]
    assert "лучший предыдущий кандидат" in prompts[2]
    assert "Замени РОВНО 1" in prompts[2]
    # Cooktime from the discarded worse retry must NOT become the new base.
    assert "cook_time=60" not in prompts[2]
    assert "Замени РОВНО 2" not in prompts[2]


def test_exhausted_targeted_retries_raise_constraint_error(monkeypatch, strategy):
    prompts: list[str] = []
    bad = _menu_with_duplicates(strategy)
    _install_client(
        monkeypatch,
        [_fake_response(bad), _fake_response(bad), _fake_response(bad)],
        prompts,
    )

    with pytest.raises(MenuConstraintError) as exc_info:
        _run(strategy)

    assert "MEAL_DUPLICATE_EXCESSIVE" in exc_info.value.issue_codes
    # Structured issues available for diagnostics; stats captured.
    assert exc_info.value.issues
    assert exc_info.value.menu_stats.get("unique_recipe_count")
    assert exc_info.value.meal_inventory.get("at_limit")
    assert len(prompts) == 3
