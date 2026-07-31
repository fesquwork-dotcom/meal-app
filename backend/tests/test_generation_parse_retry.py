"""Schema/JSON failure visibility and retry after Claude HTTP 200."""

from __future__ import annotations

import asyncio
import json
from datetime import date

import pytest

import claude_service
import config
from claude_exceptions import ClaudeValidationError
from claude_service import process_claude_response
from menu_validation import MenuValidationRequest
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict
from tests.test_anthropic_retry import _install_fake_client, make_http_response


def test_schema_validation_error_includes_details():
    request = MenuValidationRequest(
        days=1,
        budget=5000,
        meal_types=["dinner"],
        meals_per_day=1,
        persons=2,
        cooktime="30 мин",
        allergies="",
    )
    with pytest.raises(ClaudeValidationError) as exc_info:
        process_claude_response(
            json.dumps(
                {
                    "summary": "x",
                    "total_cost": 1,
                    "days_plan": [],
                    "recipes": [],
                    "basket": [],
                }
            ),
            request,
            request_id="req",
            user_id=1,
            started_at=0.0,
        )
    assert exc_info.value.details
    assert any("days_plan" in item or "recipes" in item for item in exc_info.value.details)


def test_json_parse_failure_retries_then_succeeds(monkeypatch):
    import main

    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    strategy = main._strategy_builder.build({"days": 1, "cooktime": "fast"})
    valid = json.dumps(
        annotate_cooking_metadata(
            build_valid_menu_dict(days=1, cooktime="15 мин"),
            strategy,
        ),
        ensure_ascii=False,
    )

    sleep_log: list[float] = []
    responses = [
        make_http_response(
            200,
            json_body={
                "stop_reason": "max_tokens",
                "content": [{"type": "text", "text": "{not-json"}],
            },
        ),
        make_http_response(
            200,
            json_body={
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": valid}],
            },
        ),
    ]
    _install_fake_client(monkeypatch, responses, sleep_log)

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
            plan_start_date=date(2026, 7, 18),
            user_id=1,
        )
    )
    assert result["recipes"]
