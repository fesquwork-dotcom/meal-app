"""Sprint 10.7 — safe JSON recovery regression tests."""

from __future__ import annotations

import asyncio
import json
from datetime import date

import pytest

import claude_service
import config
from claude_exceptions import ClaudeJsonError
from claude_json import extract_json_object, extract_json_object_with_meta
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict
from tests.test_anthropic_retry import make_http_response


def test_extracts_clean_json_object():
    payload = {"summary": "ok", "total_cost": 10}
    result = extract_json_object(json.dumps(payload, ensure_ascii=False))
    assert result == payload


def test_extracts_json_code_fence():
    raw = '```json\n{"summary":"ok","total_cost":1}\n```'
    result = extract_json_object(raw)
    assert result["summary"] == "ok"


def test_extracts_plain_fence():
    raw = '```\n{"summary":"ok","total_cost":1}\n```'
    result = extract_json_object(raw)
    assert result["total_cost"] == 1


def test_empty_response_raises():
    with pytest.raises(ClaudeJsonError, match="Empty"):
        extract_json_object("")


def test_array_response_raises():
    with pytest.raises(ClaudeJsonError, match="array"):
        extract_json_object("[1, 2, 3]")


def test_preamble_plus_object_recovers():
    raw = 'Вот меню:\n{"summary":"ok","total_cost":1}'
    result = extract_json_object_with_meta(raw)
    assert result.recovered is True
    assert result.payload["summary"] == "ok"
    assert result.diagnostics.recovery_mode == "preamble"


def test_object_plus_trailing_prose_recovers():
    raw = '{"summary":"ok","total_cost":1}\nГотово.'
    result = extract_json_object_with_meta(raw)
    assert result.recovered is True
    assert result.payload["total_cost"] == 1
    assert result.diagnostics.recovery_mode == "trailing"


def test_braces_inside_strings_do_not_break_scanner():
    raw = 'Note: {"summary":"has {brace} and } end","total_cost":1}'
    result = extract_json_object(raw)
    assert result["summary"] == "has {brace} and } end"


def test_escaped_quotes_handled():
    raw = 'Prefix {"summary":"say \\"hi\\"","total_cost":1}'
    result = extract_json_object(raw)
    assert result["summary"] == 'say "hi"'


def test_multiple_top_level_objects_rejected():
    raw = '{"a":1}{"b":2}'
    with pytest.raises(ClaudeJsonError, match="Ambiguous|Invalid"):
        extract_json_object(raw)


def test_malformed_json_rejected():
    with pytest.raises(ClaudeJsonError):
        extract_json_object('{"summary": "ok",')


def test_truncated_json_rejected():
    with pytest.raises(ClaudeJsonError):
        extract_json_object('{"summary":"ok","days_plan":[{"day":1')


def test_trailing_comma_not_silently_repaired():
    with pytest.raises(ClaudeJsonError):
        extract_json_object('{"summary":"ok","total_cost":1,}')


def test_nested_object_is_accepted():
    raw = json.dumps(
        {
            "summary": "ok",
            "total_cost": 1,
            "days_plan": [{"day": "День 1", "breakfast": "A", "lunch": "B", "dinner": "C"}],
            "recipes": [
                {
                    "name": "A",
                    "ingredients": [{"name": "x", "amount": "1"}],
                    "steps": ["s"],
                }
            ],
            "basket": [{"category": "c", "items": [{"name": "x", "price": 1}]}],
        }
    )
    result = extract_json_object(raw)
    assert isinstance(result["days_plan"], list)


def test_safe_recovery_does_not_consume_extra_llm_attempt(monkeypatch):
    import main

    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "test-key")
    strategy = main._strategy_builder.build({"days": 1, "cooktime": "fast"})
    valid = annotate_cooking_metadata(
        build_valid_menu_dict(days=1, cooktime="15 мин"),
        strategy,
    )
    wrapped = "Вот готовое меню:\n" + json.dumps(valid, ensure_ascii=False)

    sleep_log: list[float] = []
    call_count = {"n": 0}
    responses = [
        make_http_response(
            200,
            json_body={
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": wrapped}],
            },
        ),
    ]

    import anthropic_http

    class CountingClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            call_count["n"] += 1
            return responses.pop(0)

    async def fake_sleep(seconds):
        sleep_log.append(seconds)

    monkeypatch.setattr(anthropic_http.httpx, "AsyncClient", CountingClient)
    monkeypatch.setattr(claude_service.asyncio, "sleep", fake_sleep)

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
    assert call_count["n"] == 1
    assert claude_service.MAX_LLM_ATTEMPTS == 3
