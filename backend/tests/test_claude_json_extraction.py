import json

import pytest

from claude_exceptions import ClaudeJsonError
from claude_json import extract_json_object


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


def test_extra_text_raises():
    with pytest.raises(ClaudeJsonError):
        extract_json_object('Вот меню: {"summary":"ok","total_cost":1}')


def test_broken_json_raises():
    with pytest.raises(ClaudeJsonError):
        extract_json_object('{"summary": "ok",')


def test_two_objects_in_fences_raises():
    raw = '```json\n{"a":1}\n```\n```json\n{"b":2}\n```'
    with pytest.raises(ClaudeJsonError):
        extract_json_object(raw)


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
