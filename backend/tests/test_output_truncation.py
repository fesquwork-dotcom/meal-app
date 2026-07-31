"""Sprint 10.3.1: max_tokens truncation fail-fast, compact retry, controlled 502."""

from __future__ import annotations

import asyncio
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

import claude_service
import config
import database
import main
from claude_exceptions import ClaudeJsonError, ClaudeOutputTruncatedError
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict
from tests.profile_test_helpers import generate_with_token, issue_preview_token, save_profile
from tests.test_anthropic_retry import make_http_response

SECRET_KEY = "SECRET_KEY_MUST_NOT_APPEAR"


def _truncated_response() -> object:
    return make_http_response(
        200,
        json_body={
            "stop_reason": "max_tokens",
            "usage": {"output_tokens": 16000},
            "content": [],
        },
    )


def _valid_response(strategy) -> object:
    valid = json.dumps(
        annotate_cooking_metadata(
            build_valid_menu_dict(days=1, cooktime="15 мин"),
            strategy,
        ),
        ensure_ascii=False,
    )
    return make_http_response(
        200,
        json_body={
            "stop_reason": "end_turn",
            "usage": {"output_tokens": 2000},
            "content": [{"type": "text", "text": valid}],
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
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", SECRET_KEY)

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
    return main._strategy_builder.build({"days": 1, "cooktime": "fast"})


def test_truncated_empty_response_never_reaches_parser(monkeypatch, strategy):
    prompts: list[str] = []
    parser_calls = []
    original_extract = claude_service.extract_json_object

    def spying_extract(raw):
        parser_calls.append(raw)
        return original_extract(raw)

    monkeypatch.setattr(claude_service, "extract_json_object", spying_extract)
    _install_client(
        monkeypatch,
        [_truncated_response(), _truncated_response(), _truncated_response()],
        prompts,
    )

    with pytest.raises(ClaudeOutputTruncatedError) as exc_info:
        _run(strategy)

    assert parser_calls == []
    assert exc_info.value.stop_reason == "max_tokens"
    assert exc_info.value.output_tokens == 16000
    assert exc_info.value.raw_chars == 0


def test_truncation_retry_uses_compact_instruction_not_identical_request(monkeypatch, strategy):
    prompts: list[str] = []
    _install_client(monkeypatch, [_truncated_response(), _valid_response(strategy)], prompts)

    result = _run(strategy)

    assert result["recipes"]
    assert len(prompts) == 2
    assert prompts[0] != prompts[1]
    assert "исчерпал лимит выходных токенов" in prompts[1]
    assert "4-6 шагов" in prompts[1]


def test_truncated_midjson_classified_as_truncation_not_json_parse(monkeypatch, strategy):
    prompts: list[str] = []
    cut_json = make_http_response(
        200,
        json_body={
            "stop_reason": "max_tokens",
            "usage": {"output_tokens": 16000},
            "content": [{"type": "text", "text": '{"summary": "нач'}],
        },
    )
    _install_client(monkeypatch, [cut_json, _valid_response(strategy)], prompts)

    result = _run(strategy)
    assert result["recipes"]
    assert "исчерпал лимит выходных токенов" in prompts[1]


def test_malformed_json_without_max_tokens_stays_json_parse(monkeypatch, strategy):
    prompts: list[str] = []
    bad = make_http_response(
        200,
        json_body={
            "stop_reason": "end_turn",
            "usage": {"output_tokens": 500},
            "content": [{"type": "text", "text": "{not-json"}],
        },
    )
    _install_client(monkeypatch, [bad, bad, bad], prompts)

    with pytest.raises(ClaudeJsonError):
        _run(strategy)

    assert "не был валидным JSON" in prompts[1]
    assert "исчерпал лимит выходных токенов" not in prompts[1]


def test_thinking_disabled_in_request_body(monkeypatch, strategy):
    bodies: list[dict] = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **kwargs):
            bodies.append(kwargs["json"])
            return _valid_response(strategy)

    monkeypatch.setattr(claude_service, "create_anthropic_client", lambda: FakeClient())
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", SECRET_KEY)
    monkeypatch.setattr(config, "CLAUDE_DISABLE_THINKING", True)

    result = _run(strategy)
    assert result["recipes"]
    assert bodies[0].get("thinking") == {"type": "disabled"}


def test_thinking_flag_off_keeps_body_unchanged(monkeypatch, strategy):
    bodies: list[dict] = []

    class FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **kwargs):
            bodies.append(kwargs["json"])
            return _valid_response(strategy)

    monkeypatch.setattr(claude_service, "create_anthropic_client", lambda: FakeClient())
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", SECRET_KEY)
    monkeypatch.setattr(config, "CLAUDE_DISABLE_THINKING", False)

    result = _run(strategy)
    assert result["recipes"]
    assert "thinking" not in bodies[0]


def test_no_secrets_in_truncation_logs(monkeypatch, strategy, caplog):
    import logging

    prompts: list[str] = []
    _install_client(
        monkeypatch,
        [_truncated_response(), _truncated_response(), _truncated_response()],
        prompts,
    )

    with caplog.at_level(logging.INFO):
        with pytest.raises(ClaudeOutputTruncatedError):
            _run(strategy)

    assert SECRET_KEY not in caplog.text
    assert "output_truncated" in caplog.text
    assert "retry_mode=compact_output" in caplog.text


# --- API layer ----------------------------------------------------------------


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path, monkeypatch):
    db_path = tmp_path / "output-truncation.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


@pytest.fixture
def client():
    return TestClient(main.app)


def test_exhausted_truncation_returns_dedicated_502_code(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    async def fake_generate_menu(**_kwargs):
        raise ClaudeOutputTruncatedError(
            "truncated",
            stop_reason="max_tokens",
            output_tokens=16000,
            raw_chars=0,
        )

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = generate_with_token(client, token)
    assert response.status_code == 502
    body = response.json()
    assert body["code"] == "MENU_GENERATION_OUTPUT_TRUNCATED"
    assert body["message"] == main.USER_MESSAGE_OUTPUT_TRUNCATED
