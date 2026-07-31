"""Ingredient contribution contract: validator reasons, diagnostics, correction prompt."""

from __future__ import annotations

import asyncio
import json
import logging

import pytest

import claude_service
import config
import main
from claude_exceptions import MenuConstraintError
from menu_models import MenuPlan, RecipeIngredient
from recipe_identity import (
    CONTRIBUTION_REASON_NOT_ALLOWLISTED,
    CONTRIBUTION_REASON_PANTRY_MISMATCH,
    normalize_pantry_contribution,
    validate_ingredient_contributions,
)
from strategy.prompt import CONTRIBUTION_CORRECTION_RULE, build_correction_prompt
from strategy.replacement_prompt import (
    build_replacement_system_prompt,
)
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict


def _strategy():
    return main._strategy_builder.build({"days": 1, "cooktime": "fast"})


def _annotated_menu(strategy) -> dict:
    return annotate_cooking_metadata(
        build_valid_menu_dict(days=1, cooktime="15 мин"), strategy
    )


def _menu_with_ingredient(strategy, ingredient: dict) -> MenuPlan:
    menu_dict = _annotated_menu(strategy)
    for recipe in menu_dict["recipes"]:
        for ing in recipe["ingredients"]:
            ing.setdefault("contribution", "purchase")
        recipe["ingredients"].append(ingredient)
    return MenuPlan.model_validate(menu_dict)


# --- root cause: pantry contract ------------------------------------------------


@pytest.mark.parametrize(
    "name",
    ["Паприка", "Кумин", "Зелень", "Фета", "Мёд", "Смесь специй", "Гарам масала"],
)
def test_named_spices_are_not_pantry_staples(name):
    """Confirmed root cause: model marks these pantry, normalizer says purchase."""
    ingredient = RecipeIngredient(name=name, amount="10 г", contribution="pantry")
    assert normalize_pantry_contribution(ingredient) == "purchase"


@pytest.mark.parametrize(
    "name",
    ["Соль", "Вода", "Оливковое масло", "Черный перец", "Специи"],
)
def test_real_staples_stay_pantry(name):
    ingredient = RecipeIngredient(name=name, amount="10 г", contribution="pantry")
    assert normalize_pantry_contribution(ingredient) == "pantry"


def test_pantry_mismatch_produces_reason_code():
    strategy = _strategy()
    menu = _menu_with_ingredient(
        strategy, {"name": "Паприка", "amount": "5 г", "contribution": "pantry"}
    )
    issues = validate_ingredient_contributions(menu, strategy_aware=True)
    contribution_issues = [
        issue for issue in issues if issue.code == "INGREDIENT_CONTRIBUTION_INVALID"
    ]
    assert contribution_issues
    for issue in contribution_issues:
        assert issue.reason_code == CONTRIBUTION_REASON_PANTRY_MISMATCH
        assert issue.severity == "error"
        assert "Паприка" in issue.message
        assert issue.path


def test_valid_purchase_and_pantry_staple_pass():
    strategy = _strategy()
    menu = _menu_with_ingredient(
        strategy, {"name": "Соль", "amount": "по вкусу", "contribution": "pantry"}
    )
    issues = validate_ingredient_contributions(menu, strategy_aware=True)
    assert not [i for i in issues if i.code == "INGREDIENT_CONTRIBUTION_INVALID"]


def test_non_allowlisted_value_reason_code():
    """Unreachable via Claude (Pydantic rejects earlier) but validator stays strict."""
    strategy = _strategy()
    menu = _menu_with_ingredient(
        strategy, {"name": "Сыр", "amount": "100 г", "contribution": "purchase"}
    )
    bad = menu.recipes[0].ingredients[-1].model_copy()
    object.__setattr__(bad, "contribution", "optional")  # bypass validation deliberately
    menu.recipes[0].ingredients[-1] = bad
    issues = validate_ingredient_contributions(menu, strategy_aware=True)
    target = [
        issue
        for issue in issues
        if issue.code == "INGREDIENT_CONTRIBUTION_INVALID"
        and issue.reason_code == CONTRIBUTION_REASON_NOT_ALLOWLISTED
    ]
    assert target


def test_pydantic_rejects_non_enum_contribution():
    """Layer alignment: schema rejects unknown values before the validator."""
    with pytest.raises(ValueError):
        RecipeIngredient(name="Сыр", amount="100 г", contribution="по вкусу")


# --- diagnostics logging ---------------------------------------------------------


def test_diagnostic_log_contains_reason_and_safe_label(caplog):
    strategy = _strategy()
    menu = _menu_with_ingredient(
        strategy,
        {"name": "Паприка\x00копчёная" + "x" * 100, "amount": "5 г", "contribution": "pantry"},
    )
    with caplog.at_level(logging.WARNING):
        validate_ingredient_contributions(menu, strategy_aware=True)

    text = caplog.text
    assert "ingredient_contribution_invalid" in text
    assert "validation_reason=PANTRY_CONTRACT_MISMATCH" in text
    assert "\x00" not in text
    # Truncated to 40 chars: the raw 100-char tail must not be present.
    assert "x" * 41 not in text


def test_diagnostic_log_hides_name_in_production(monkeypatch, caplog):
    monkeypatch.setattr(config, "ENVIRONMENT", "production")
    strategy = _strategy()
    menu = _menu_with_ingredient(
        strategy, {"name": "Паприка", "amount": "5 г", "contribution": "pantry"}
    )
    with caplog.at_level(logging.WARNING):
        validate_ingredient_contributions(menu, strategy_aware=True)

    matching = [
        record.getMessage()
        for record in caplog.records
        if "ingredient_contribution_invalid" in record.getMessage()
    ]
    assert matching
    for message in matching:
        assert "Паприка" not in message
        assert "ingredient_label" not in message
        assert "validation_reason=PANTRY_CONTRACT_MISMATCH" in message


def test_validation_failure_log_includes_reason_codes_and_request_id(caplog):
    strategy = _strategy()
    menu_dict = _annotated_menu(strategy)
    for recipe in menu_dict["recipes"]:
        for ing in recipe["ingredients"]:
            ing.setdefault("contribution", "purchase")
        recipe["ingredients"].append(
            {"name": "Кумин", "amount": "3 г", "contribution": "pantry"}
        )

    from menu_validation import MenuValidationRequest

    request = MenuValidationRequest(
        days=1,
        budget=strategy.budget,
        meal_types=list(strategy.meal_types),
        meals_per_day=strategy.meals_per_day,
        persons=2,
        cooktime="fast",
        allergies="нет",
        strategy_aware=True,
    )

    with caplog.at_level(logging.WARNING):
        with pytest.raises(MenuConstraintError) as exc_info:
            claude_service.process_claude_response(
                json.dumps(menu_dict, ensure_ascii=False),
                request,
                "req-contract-1",
                42,
                0.0,
                strategy=strategy,
            )

    assert "INGREDIENT_CONTRIBUTION_INVALID" in exc_info.value.issue_codes
    assert exc_info.value.issue_messages  # details available for correction prompt
    assert "request_id=req-contract-1" in caplog.text
    assert "PANTRY_CONTRACT_MISMATCH" in caplog.text


# --- correction prompt ------------------------------------------------------------


def test_correction_prompt_contains_specific_rule_and_path():
    strategy = _strategy()
    prompt = build_correction_prompt(
        ["INGREDIENT_CONTRIBUTION_INVALID"],
        ["Ingredient 'Паприка' cannot be pantry (path: recipes[Шакшука].ingredients[7])"],
        strategy,
    )
    assert "ПРАВИЛО INGREDIENT CONTRIBUTION" in prompt
    assert "Паприка" in prompt
    assert "recipes[Шакшука].ingredients[7]" in prompt
    assert "purchase" in prompt
    assert "Верни полный исправленный JSON" in prompt


def test_correction_prompt_without_contribution_code_unchanged():
    strategy = _strategy()
    prompt = build_correction_prompt(
        ["STRATEGY_DAYS_COUNT_MISMATCH"],
        ["bad days"],
        strategy,
    )
    assert "ПРАВИЛО INGREDIENT CONTRIBUTION" not in prompt


def test_correction_rule_matches_actual_validator_contract():
    """The rule text must reflect PANTRY_STAPLES, not an invented numeric contract."""
    assert "соль" in CONTRIBUTION_CORRECTION_RULE
    assert "purchase" in CONTRIBUTION_CORRECTION_RULE
    assert "from_source" in CONTRIBUTION_CORRECTION_RULE
    # No numeric-contribution vocabulary: contribution is categorical here.
    assert "число" not in CONTRIBUTION_CORRECTION_RULE.lower()


def test_replacement_system_prompt_contains_contribution_contract():
    strategy = _strategy()
    prompt = build_replacement_system_prompt(strategy)
    assert "contribution" in prompt
    assert "pantry" in prompt
    assert "purchase" in prompt


# --- end-to-end mocked correction loop --------------------------------------------


def _menu_json_with_contribution(strategy, contribution_ing: dict | None) -> str:
    menu_dict = _annotated_menu(strategy)
    for recipe in menu_dict["recipes"]:
        for ing in recipe["ingredients"]:
            ing.setdefault("contribution", "purchase")
        if contribution_ing is not None:
            recipe["ingredients"] = recipe["ingredients"] + [dict(contribution_ing)]
    menu_dict["plan_start_date"] = "2099-01-01"
    return json.dumps(menu_dict, ensure_ascii=False)


def _run_generation_with_responses(monkeypatch, strategy, bodies: list[str], prompts: list[str]):
    class FakeResponse:
        status_code = 200

        def __init__(self, body: str):
            self._body = body

        def json(self):
            return {"content": [{"type": "text", "text": self._body}]}

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **kwargs):
            prompts.append(kwargs["json"]["messages"][0]["content"])
            return FakeResponse(bodies.pop(0))

    monkeypatch.setattr("anthropic_http.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")

    from datetime import date

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
            plan_start_date=date(2026, 7, 13),
        )
    )


def test_invalid_pantry_then_corrected_succeeds(monkeypatch):
    strategy = _strategy()
    prompts: list[str] = []
    bodies = [
        _menu_json_with_contribution(
            strategy, {"name": "Паприка", "amount": "5 г", "contribution": "pantry"}
        ),
        _menu_json_with_contribution(
            strategy, {"name": "Паприка", "amount": "5 г", "contribution": "purchase"}
        ),
    ]

    result = _run_generation_with_responses(monkeypatch, strategy, bodies, prompts)

    assert result["days_plan"]
    assert len(prompts) == 2
    # Second attempt must carry the deterministic rule and the actual ingredient.
    assert "ПРАВИЛО INGREDIENT CONTRIBUTION" in prompts[1]
    assert "Паприка" in prompts[1]
    assert "path:" in prompts[1]


def test_three_invalid_attempts_controlled_failure(monkeypatch):
    strategy = _strategy()
    prompts: list[str] = []
    invalid = _menu_json_with_contribution(
        strategy, {"name": "Кумин", "amount": "3 г", "contribution": "pantry"}
    )
    bodies = [invalid, invalid, invalid]

    with pytest.raises(MenuConstraintError) as exc_info:
        _run_generation_with_responses(monkeypatch, strategy, bodies, prompts)

    assert len(prompts) == claude_service.MAX_LLM_ATTEMPTS
    assert "INGREDIENT_CONTRIBUTION_INVALID" in exc_info.value.issue_codes


def test_multiple_invalid_ingredients_all_reported(monkeypatch):
    strategy = _strategy()
    prompts: list[str] = []
    menu_dict = _annotated_menu(strategy)
    for recipe in menu_dict["recipes"]:
        for ing in recipe["ingredients"]:
            ing.setdefault("contribution", "purchase")
    menu_dict["recipes"][0]["ingredients"].append(
        {"name": "Паприка", "amount": "5 г", "contribution": "pantry"}
    )
    menu_dict["recipes"][0]["ingredients"].append(
        {"name": "Фета", "amount": "50 г", "contribution": "pantry"}
    )
    menu_dict["plan_start_date"] = "2099-01-01"
    invalid = json.dumps(menu_dict, ensure_ascii=False)
    valid = _menu_json_with_contribution(strategy, None)

    result = _run_generation_with_responses(monkeypatch, strategy, [invalid, valid], prompts)

    assert result["days_plan"]
    assert "Паприка" in prompts[1]
    assert "Фета" in prompts[1]
