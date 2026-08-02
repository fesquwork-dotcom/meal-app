"""Safe Anthropic error parsing and privacy-preserving logging."""

import asyncio
import json
import logging

import httpx
import pytest

import claude_service
import config
from anthropic_http import parse_anthropic_error
from claude_exceptions import ClaudeUnavailableError


def make_response(
    status_code: int,
    *,
    json_body: dict | None = None,
    text_body: str | None = None,
    request_id: str | None = "req_test_123",
) -> httpx.Response:
    headers = {}
    if request_id is not None:
        headers["request-id"] = request_id
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    if json_body is not None:
        return httpx.Response(
            status_code,
            json=json_body,
            headers=headers,
            request=request,
        )
    return httpx.Response(
        status_code,
        text=text_body or "",
        headers=headers,
        request=request,
    )


def anthropic_error_body(error_type: str, message: str) -> dict:
    return {"type": "error", "error": {"type": error_type, "message": message}}


# --- parser: standard Anthropic error payloads --------------------------------


@pytest.mark.parametrize(
    "status,error_type",
    [
        (401, "authentication_error"),
        (403, "permission_error"),
        (404, "not_found_error"),
        (429, "rate_limit_error"),
        (500, "api_error"),
    ],
)
def test_parses_known_anthropic_error_types(status, error_type):
    response = make_response(
        status, json_body=anthropic_error_body(error_type, "provider says no")
    )
    parsed = parse_anthropic_error(response)
    assert parsed.status_code == status
    assert parsed.error_type == error_type
    assert parsed.error_message == "provider says no"
    assert parsed.anthropic_request_id == "req_test_123"


def test_non_json_body_gives_unknown_type_and_truncated_text():
    response = make_response(502, text_body="<html>Bad gateway</html>")
    parsed = parse_anthropic_error(response)
    assert parsed.error_type == "unknown"
    assert parsed.error_message == "<html>Bad gateway</html>"


def test_empty_body_gives_no_body_marker():
    response = make_response(500, text_body="")
    parsed = parse_anthropic_error(response)
    assert parsed.error_type == "unknown"
    assert parsed.error_message == "no_body"


def test_very_long_message_is_truncated_to_500():
    response = make_response(
        403, json_body=anthropic_error_body("permission_error", "x" * 5000)
    )
    parsed = parse_anthropic_error(response)
    assert parsed.error_message is not None
    assert len(parsed.error_message) == 500


def test_control_characters_are_removed():
    response = make_response(
        403,
        json_body=anthropic_error_body("permission_error", "bad\x00msg\r\nline\x1b"),
    )
    parsed = parse_anthropic_error(response)
    assert parsed.error_message is not None
    assert "\x00" not in parsed.error_message
    assert "\r" not in parsed.error_message
    assert "\n" not in parsed.error_message
    assert "\x1b" not in parsed.error_message


def test_missing_request_id_is_none():
    response = make_response(
        403,
        json_body=anthropic_error_body("permission_error", "denied"),
        request_id=None,
    )
    parsed = parse_anthropic_error(response)
    assert parsed.anthropic_request_id is None


def test_unexpected_error_type_is_sanitized_not_rejected():
    response = make_response(
        400, json_body=anthropic_error_body("weird_new_type", "hm")
    )
    parsed = parse_anthropic_error(response)
    assert parsed.error_type == "weird_new_type"


# --- generation path: safe logging on provider 403 ----------------------------


SECRET_KEY_MARKER = "SECRET_KEY_MUST_NOT_APPEAR"
SECRET_PROMPT_MARKER = "SECRET_PROMPT_MUST_NOT_APPEAR"


def run_generation_expecting_failure(monkeypatch, status_code: int, error_body: dict):
    class FakeResponse:
        def __init__(self):
            self.status_code = status_code
            self.headers = httpx.Headers({"request-id": "req_prov_42"})
            self.text = json.dumps(error_body)

        def json(self):
            return error_body

    class FakeAsyncClient:
        def __init__(self, *_args, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def post(self, *_args, **_kwargs):
            return FakeResponse()

    monkeypatch.setattr("anthropic_http.httpx.AsyncClient", FakeAsyncClient)
    monkeypatch.setattr(config, "ANTHROPIC_API_KEY", SECRET_KEY_MARKER)

    with pytest.raises(ClaudeUnavailableError):
        asyncio.run(
            claude_service.generate_menu(
                budget=5000,
                days=1,
                meal_types=["breakfast", "lunch", "dinner"],
                meals_per_day=3,
                persons=2,
                proteins=["chicken"],
                goal="home",
                cooktime="fast",
                allergies=SECRET_PROMPT_MARKER,
            )
        )


def test_403_logs_permission_error_details(monkeypatch, caplog):
    with caplog.at_level(logging.ERROR):
        run_generation_expecting_failure(
            monkeypatch,
            403,
            anthropic_error_body("permission_error", "Request not allowed"),
        )
    log_text = caplog.text
    assert "generation_failed" in log_text
    assert "configured_model=" in log_text
    assert "provider_error_type=permission_error" in log_text
    assert "provider_message=Request not allowed" in log_text
    assert "provider_request_id=req_prov_42" in log_text


def test_401_logs_authentication_error(monkeypatch, caplog):
    with caplog.at_level(logging.ERROR):
        run_generation_expecting_failure(
            monkeypatch,
            401,
            anthropic_error_body("authentication_error", "invalid x-api-key"),
        )
    assert "provider_error_type=authentication_error" in caplog.text


def test_logs_never_contain_secrets_or_prompts(monkeypatch, caplog):
    with caplog.at_level(logging.DEBUG):
        run_generation_expecting_failure(
            monkeypatch,
            403,
            anthropic_error_body("permission_error", "denied"),
        )
    log_text = caplog.text
    assert SECRET_KEY_MARKER not in log_text
    assert SECRET_PROMPT_MARKER not in log_text
    assert "x-api-key" not in log_text
    assert "ANTHROPIC_API_KEY" not in log_text
    assert "Authorization" not in log_text
