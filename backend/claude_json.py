"""Strict JSON extraction from Claude text responses."""

from __future__ import annotations

import json
import re

from claude_exceptions import ClaudeJsonError

_FENCE_PATTERN = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


def _parse_object(candidate: str) -> dict[str, object]:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise ClaudeJsonError("Invalid JSON in Claude response") from exc

    if isinstance(parsed, list):
        raise ClaudeJsonError("Expected JSON object, got array")
    if not isinstance(parsed, dict):
        raise ClaudeJsonError("Expected JSON object")
    return parsed


def extract_json_object(raw_text: str) -> dict[str, object]:
    """Extracts exactly one JSON object from Claude text.

    Accepts pure JSON or a single fenced block. Does not repair broken JSON.
    """
    if not raw_text or not raw_text.strip():
        raise ClaudeJsonError("Empty Claude response")

    stripped = raw_text.strip()
    candidates: list[str] = []

    if stripped.startswith("{"):
        try:
            _parse_object(stripped)
            candidates.append(stripped)
        except ClaudeJsonError:
            pass

    fence_match = _FENCE_PATTERN.match(stripped)
    if fence_match:
        inner = fence_match.group(1).strip()
        if inner and inner not in candidates:
            try:
                _parse_object(inner)
                candidates.append(inner)
            except ClaudeJsonError:
                pass

    if len(candidates) > 1:
        raise ClaudeJsonError("Ambiguous JSON: multiple valid object candidates")

    if len(candidates) == 1:
        return _parse_object(candidates[0])

    try:
        parsed = json.loads(stripped)
        if isinstance(parsed, list):
            raise ClaudeJsonError("Expected JSON object, got array")
    except json.JSONDecodeError:
        pass

    raise ClaudeJsonError("Invalid JSON in Claude response")
