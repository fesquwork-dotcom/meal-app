import asyncio
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

import claude_service
import config
import database
import main
from claude_exceptions import MenuConstraintError
from strategy.exceptions import StrategyComplianceError, StrategyValidationError
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict
from tests.profile_test_helpers import generate_with_token, issue_preview_token, save_profile


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _configure_auth_and_db(tmp_path, monkeypatch):
    db_path = tmp_path / "strategy-integration.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


def test_generate_menu_pipeline_calls_strategy_builder_once(client, monkeypatch):
    build_calls = 0
    original_build_with_reasons = main._strategy_builder.build_with_reasons_from_inputs

    def counting_build_with_reasons(profile, memory_context=None, behavior_context=None, learned_context=None):
        nonlocal build_calls
        build_calls += 1
        return original_build_with_reasons(profile, memory_context, behavior_context, learned_context)

    captured: dict[str, object] = {}

    async def fake_generate_menu(**kwargs):
        captured.update(kwargs)
        menu = build_valid_menu_dict(days=kwargs["days"])
        menu["plan_start_date"] = kwargs["plan_start_date"].isoformat()
        return menu

    async def fake_save_profile(_user_id, _profile):
        return None

    monkeypatch.setattr(
        main._strategy_builder, "build_with_reasons_from_inputs", counting_build_with_reasons
    )
    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    monkeypatch.setattr("main.database.save_profile", fake_save_profile)

    save_profile(client, expected_revision=0)
    token = issue_preview_token(client, plan_start_date="2026-07-13")
    build_calls = 0
    response = generate_with_token(client, token)

    assert response.status_code == 200
    assert build_calls == 1
    assert "strategy" in captured
    assert captured["strategy"].meal_types == ["breakfast", "lunch", "dinner"]
    assert captured["plan_start_date"].isoformat() == "2026-07-13"
    assert response.json()["plan_start_date"] == "2026-07-13"
    assert response.json().get("strategy_id")


def test_invalid_strategy_blocks_generate_menu_and_returns_422(client, monkeypatch):
    generate_calls = 0

    async def fake_generate_menu(**_kwargs):
        nonlocal generate_calls
        generate_calls += 1
        return build_valid_menu_dict(days=1)

    def failing_validation(*_args, **_kwargs):
        raise StrategyValidationError("conflict", code="STRATEGY_DAYS_MISMATCH")

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    monkeypatch.setattr(main, "validate_strategy_for_request", failing_validation)

    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)
    response = generate_with_token(client, token)

    assert response.status_code == 422
    assert generate_calls == 0


def test_invalid_plan_start_date_in_preview_returns_422(client):
    save_profile(client, expected_revision=0)
    response = client.post(
        "/api/strategy/preview",
        json={"plan_start_date": "2026-02-31"},
    )
    assert response.status_code == 422


def test_strategy_aware_prompt_uses_weekly_strategy_section(monkeypatch):
    strategy = main._strategy_builder.build(
        {"days": 2, "budget": 2000, "goal": "home", "meal_types": ["breakfast", "dinner"]}
    )
    prompt = claude_service.build_prompt(
        strategy.budget,
        strategy.days,
        list(strategy.meal_types),
        persons=2,
        proteins=list(strategy.preferred_proteins),
        goal=strategy.goal,
        cooktime="medium",
        allergies="нет",
        strategy=strategy,
        store="any",
    )

    assert "WEEKLY_STRATEGY" in prompt
    assert '"goal": "home"' in prompt
    assert "meal_id" in prompt
    assert "requires_cooking" in prompt
    assert "plan_start_date" not in prompt
    assert "Бюджет на весь период" not in prompt
    assert "Исключить:" not in prompt


def test_legacy_prompt_without_strategy_keeps_profile_fields():
    prompt = claude_service.build_prompt(
        3000,
        3,
        ["breakfast", "lunch", "dinner"],
        persons=2,
        proteins=["any"],
        goal="home",
        cooktime="medium",
        allergies="нет",
        strategy=None,
    )

    assert "Бюджет на весь период" in prompt
    assert "WEEKLY_STRATEGY" not in prompt


def test_compliance_violation_triggers_correction_retry(monkeypatch):
    strategy = main._strategy_builder.build({"days": 1, "cooktime": "fast"})
    calls: list[str] = []
    menu_json = json.dumps(build_valid_menu_dict(days=1, cooktime="15 мин"), ensure_ascii=False)

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "content": [
                    {
                        "type": "text",
                        "text": menu_json,
                    }
                ]
            }

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **kwargs):
            calls.append(kwargs["json"]["messages"][0]["content"])
            return FakeResponse()

    def failing_compliance(_menu, _strategy):
        raise StrategyComplianceError(
            "violation",
            issues=[
                type(
                    "Issue",
                    (),
                    {
                        "code": "STRATEGY_DAYS_COUNT_MISMATCH",
                        "message": "bad",
                        "path": "days_plan",
                    },
                )()
            ],
        )

    monkeypatch.setattr("anthropic_http.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(claude_service, "validate_menu_against_strategy", failing_compliance)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")

    with pytest.raises(MenuConstraintError):
        asyncio.run(
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
            )
        )

    assert len(calls) == claude_service.MAX_LLM_ATTEMPTS
    assert "ИСПРАВЛЕНИЕ" in calls[1]
    assert "WEEKLY_STRATEGY" in calls[1]


def test_successful_generation_uses_single_llm_call(monkeypatch):
    strategy = main._strategy_builder.build({"days": 1, "cooktime": "fast"})
    call_count = 0
    menu_json = json.dumps(
        {
            **annotate_cooking_metadata(build_valid_menu_dict(days=1, cooktime="15 мин"), strategy),
            "plan_start_date": "2099-01-01",
        },
        ensure_ascii=False,
    )

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"content": [{"type": "text", "text": menu_json}]}

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            nonlocal call_count
            call_count += 1
            return FakeResponse()

    monkeypatch.setattr("anthropic_http.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")

    result = asyncio.run(
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

    assert call_count == 1
    assert result["days_plan"]
    assert result["plan_start_date"] == "2026-07-13"


def test_plan_start_date_survives_correction_retry(monkeypatch):
    strategy = main._strategy_builder.build({"days": 1, "cooktime": "fast"})
    call_count = 0
    menu_json = json.dumps(
        annotate_cooking_metadata(build_valid_menu_dict(days=1, cooktime="15 мин"), strategy),
        ensure_ascii=False,
    )

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {"content": [{"type": "text", "text": menu_json}]}

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    def flaky_compliance(_menu, _strategy):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise StrategyComplianceError(
                "violation",
                issues=[
                    type(
                        "Issue",
                        (),
                        {"code": "STRATEGY_DAYS_COUNT_MISMATCH", "message": "bad", "path": "days_plan"},
                    )()
                ],
            )

    monkeypatch.setattr("anthropic_http.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(claude_service, "validate_menu_against_strategy", flaky_compliance)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")

    result = asyncio.run(
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

    assert call_count == 2
    assert result["plan_start_date"] == "2026-07-13"
