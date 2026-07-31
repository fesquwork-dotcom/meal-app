"""Anthropic transient-status retry: generation and replacement share one policy."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date

import httpx
import pytest

import claude_service
import config
from anthropic_http import (
    RETRYABLE_ANTHROPIC_STATUS_CODES,
    compute_retry_delay_seconds,
    is_retryable_anthropic_status,
)
from claude_exceptions import ClaudeUnavailableError
from strategy.replacement_constants import MAX_REPLACEMENT_LLM_ATTEMPTS
from strategy.replacement_service import MealReplacementService
from tests.menu_fixtures import annotate_cooking_metadata, build_valid_menu_dict

SECRET_KEY = "SECRET_KEY_MUST_NOT_APPEAR"
SECRET_PROMPT = "SECRET_PROMPT_MUST_NOT_APPEAR"


def anthropic_error_body(error_type: str, message: str = "transient") -> dict:
    return {"type": "error", "error": {"type": error_type, "message": message}}


def make_http_response(
    status_code: int,
    *,
    json_body: dict | None = None,
    text_body: str = "",
    headers: dict | None = None,
) -> httpx.Response:
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    hdrs = headers or {}
    if json_body is not None:
        return httpx.Response(status_code, json=json_body, headers=hdrs, request=request)
    return httpx.Response(status_code, text=text_body, headers=hdrs, request=request)


# --- pure helpers -------------------------------------------------------------


def test_retryable_status_set():
    assert RETRYABLE_ANTHROPIC_STATUS_CODES == frozenset({429, 502, 503, 504, 529})
    for code in (429, 502, 503, 504, 529):
        assert is_retryable_anthropic_status(code)
    for code in (400, 401, 403, 404, 200):
        assert not is_retryable_anthropic_status(code)


def test_backoff_schedule_without_retry_after():
    assert compute_retry_delay_seconds(1) == 5.0
    assert compute_retry_delay_seconds(2) == 10.0
    assert compute_retry_delay_seconds(3) == 20.0


def test_retry_after_respected_and_capped():
    response = make_http_response(529, json_body={}, headers={"retry-after": "12"})
    assert compute_retry_delay_seconds(1, response) == 12.0

    capped = make_http_response(529, json_body={}, headers={"retry-after": "90"})
    assert compute_retry_delay_seconds(1, capped) == 30.0


# --- generation helpers -------------------------------------------------------


def _valid_menu_json(strategy) -> str:
    return json.dumps(
        {
            **annotate_cooking_metadata(
                build_valid_menu_dict(days=1, cooktime="15 мин"), strategy
            ),
            "plan_start_date": "2099-01-01",
        },
        ensure_ascii=False,
    )


def _install_fake_client(monkeypatch, responses: list, sleep_log: list[float]):
    """responses: list of httpx.Response or callables returning Response."""
    import anthropic_http

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            item = responses.pop(0)
            return item() if callable(item) else item

    async def fake_sleep(seconds):
        sleep_log.append(seconds)

    monkeypatch.setattr(anthropic_http.httpx, "AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(claude_service.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", SECRET_KEY)


def _run_generate(strategy, *, allergies: str = "нет"):
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
            allergies=allergies,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
            user_id=42,
        )
    )


@pytest.fixture
def strategy():
    import main

    return main._strategy_builder.build({"days": 1, "cooktime": "fast"})


def test_529_retries_then_succeeds(monkeypatch, strategy, caplog):
    sleep_log: list[float] = []
    menu_json = _valid_menu_json(strategy)
    call_count = 0
    request_ids: list[str] = []

    def first():
        nonlocal call_count
        call_count += 1
        return make_http_response(
            529,
            json_body=anthropic_error_body("overloaded_error"),
            headers={"request-id": "prov_1"},
        )

    def second():
        nonlocal call_count
        call_count += 1
        return make_http_response(
            200,
            json_body={"content": [{"type": "text", "text": menu_json}]},
        )

    original_uuid = claude_service.uuid.uuid4

    def tracking_uuid():
        value = original_uuid()
        request_ids.append(str(value))
        return value

    monkeypatch.setattr(claude_service.uuid, "uuid4", tracking_uuid)
    _install_fake_client(monkeypatch, [first, second], sleep_log)

    with caplog.at_level(logging.WARNING):
        result = _run_generate(strategy)

    assert result["days_plan"]
    assert call_count == 2
    assert sleep_log == [5.0]
    assert "anthropic_retry" in caplog.text
    assert "status=529" in caplog.text
    assert "provider_error_type=overloaded_error" in caplog.text
    assert "delay_seconds=5.0" in caplog.text or "delay_seconds=5" in caplog.text
    assert len(request_ids) == 1


def test_529_three_times_controlled_failure(monkeypatch, strategy, caplog):
    sleep_log: list[float] = []
    calls = 0

    def always_529():
        nonlocal calls
        calls += 1
        return make_http_response(
            529, json_body=anthropic_error_body("overloaded_error")
        )

    _install_fake_client(
        monkeypatch,
        [always_529, always_529, always_529],
        sleep_log,
    )

    with caplog.at_level(logging.WARNING):
        with pytest.raises(ClaudeUnavailableError):
            _run_generate(strategy)

    assert calls == claude_service.MAX_LLM_ATTEMPTS
    assert sleep_log == [5.0, 10.0]
    assert caplog.text.count("anthropic_retry") == 2
    assert "generation_failed" in caplog.text


@pytest.mark.parametrize(
    "status,error_type",
    [(503, "api_error"), (429, "rate_limit_error")],
)
def test_retryable_statuses_retry_once(monkeypatch, strategy, status, error_type):
    sleep_log: list[float] = []
    menu_json = _valid_menu_json(strategy)
    calls = 0

    def fail_once():
        nonlocal calls
        calls += 1
        return make_http_response(status, json_body=anthropic_error_body(error_type))

    def ok():
        nonlocal calls
        calls += 1
        return make_http_response(
            200, json_body={"content": [{"type": "text", "text": menu_json}]}
        )

    _install_fake_client(monkeypatch, [fail_once, ok], sleep_log)
    result = _run_generate(strategy)
    assert result["days_plan"]
    assert calls == 2
    assert sleep_log == [5.0]


def test_403_does_not_retry(monkeypatch, strategy):
    sleep_log: list[float] = []
    calls = 0

    def forbidden():
        nonlocal calls
        calls += 1
        return make_http_response(
            403, json_body=anthropic_error_body("permission_error", "denied")
        )

    _install_fake_client(monkeypatch, [forbidden], sleep_log)

    with pytest.raises(ClaudeUnavailableError):
        _run_generate(strategy)

    assert calls == 1
    assert sleep_log == []


def test_retry_after_header_used_for_delay(monkeypatch, strategy):
    sleep_log: list[float] = []
    menu_json = _valid_menu_json(strategy)

    responses = [
        make_http_response(
            529,
            json_body=anthropic_error_body("overloaded_error"),
            headers={"retry-after": "7"},
        ),
        make_http_response(
            200, json_body={"content": [{"type": "text", "text": menu_json}]}
        ),
    ]
    _install_fake_client(monkeypatch, list(responses), sleep_log)
    _run_generate(strategy)
    assert sleep_log == [7.0]


def test_same_request_id_across_retries(monkeypatch, strategy, caplog):
    sleep_log: list[float] = []
    menu_json = _valid_menu_json(strategy)
    fixed = "fixed-generation-request-id"

    class FixedUUID:
        def __str__(self):
            return fixed

    monkeypatch.setattr(claude_service.uuid, "uuid4", lambda: FixedUUID())
    _install_fake_client(
        monkeypatch,
        [
            make_http_response(529, json_body=anthropic_error_body("overloaded_error")),
            make_http_response(
                200, json_body={"content": [{"type": "text", "text": menu_json}]}
            ),
        ],
        sleep_log,
    )

    with caplog.at_level(logging.WARNING):
        _run_generate(strategy)

    assert f"request_id={fixed}" in caplog.text
    assert caplog.text.count(f"request_id={fixed}") >= 1


def test_successful_path_returns_once_no_extra_persist(monkeypatch, strategy):
    """Retries stay inside generate_menu; caller receives a single successful result."""
    sleep_log: list[float] = []
    menu_json = _valid_menu_json(strategy)
    process_calls = 0
    original = claude_service.process_claude_response

    def counting_process(*args, **kwargs):
        nonlocal process_calls
        process_calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(claude_service, "process_claude_response", counting_process)
    _install_fake_client(
        monkeypatch,
        [
            make_http_response(529, json_body=anthropic_error_body("overloaded_error")),
            make_http_response(
                200, json_body={"content": [{"type": "text", "text": menu_json}]}
            ),
        ],
        sleep_log,
    )

    result = _run_generate(strategy)
    assert process_calls == 1
    assert result["plan_start_date"] == "2026-07-13"


def test_retry_logs_have_no_secrets(monkeypatch, strategy, caplog):
    sleep_log: list[float] = []
    _install_fake_client(
        monkeypatch,
        [
            make_http_response(529, json_body=anthropic_error_body("overloaded_error")),
            make_http_response(529, json_body=anthropic_error_body("overloaded_error")),
            make_http_response(529, json_body=anthropic_error_body("overloaded_error")),
        ],
        sleep_log,
    )

    with caplog.at_level(logging.DEBUG):
        with pytest.raises(ClaudeUnavailableError):
            _run_generate(strategy, allergies=SECRET_PROMPT)

    text = caplog.text
    assert SECRET_KEY not in text
    assert SECRET_PROMPT not in text
    assert "x-api-key" not in text
    assert "Authorization" not in text


# --- replacement --------------------------------------------------------------


def test_replacement_uses_same_retry_policy(monkeypatch, caplog):
    sleep_log: list[float] = []
    calls = 0
    ok_payload = json.dumps(
        {
            "replacement": {
                "meal": {
                    "type": "dinner",
                    "recipe_name": "X",
                    "meal_id": "day1_dinner",
                    "requires_cooking": True,
                    "prepared_on_day": 1,
                    "uses_leftovers": False,
                    "source_meal_id": None,
                },
                "recipe": {
                    "name": "X",
                    "emoji": "🍲",
                    "cook_time": "20 мин",
                    "kbju": "Б:10г Ж:5г У:20г",
                    "ingredients": [{"name": "a", "amount": "1"}],
                    "steps": ["1"],
                },
            },
            "affected_meals": [],
        },
        ensure_ascii=False,
    )

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            nonlocal calls
            calls += 1
            if calls < 3:
                return make_http_response(
                    529, json_body=anthropic_error_body("overloaded_error")
                )
            return make_http_response(
                200, json_body={"content": [{"type": "text", "text": ok_payload}]}
            )

    async def fake_sleep(seconds):
        sleep_log.append(seconds)

    monkeypatch.setattr("anthropic_http.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("strategy.replacement_service.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", SECRET_KEY)

    service = MealReplacementService()
    with caplog.at_level(logging.WARNING):
        text = asyncio.run(
            service._call_claude("system", "prompt", request_id="rep-req-1")
        )

    assert "X" in text or ok_payload in text or text  # got text blocks
    assert calls == 3
    assert sleep_log == [5.0, 10.0]
    assert "anthropic_retry" in caplog.text
    assert "request_id=rep-req-1" in caplog.text
    assert SECRET_KEY not in caplog.text


def test_replacement_exhausted_retries_raise(monkeypatch):
    sleep_log: list[float] = []

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return make_http_response(
                529, json_body=anthropic_error_body("overloaded_error")
            )

    async def fake_sleep(seconds):
        sleep_log.append(seconds)

    monkeypatch.setattr("anthropic_http.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr("strategy.replacement_service.asyncio.sleep", fake_sleep)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", "key")

    service = MealReplacementService()
    with pytest.raises(ClaudeUnavailableError):
        asyncio.run(service._call_claude("s", "p", request_id="r2"))

    assert len(sleep_log) == MAX_REPLACEMENT_LLM_ATTEMPTS - 1
