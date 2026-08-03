"""Strict JSON extraction with safe wrapper recovery (Sprint 10.7).

Does NOT invent braces, strip arbitrary commas, or repair broken escapes.
Only unwraps common serialization wrappers around one complete JSON object.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass, field
from typing import Any

from claude_exceptions import ClaudeJsonError

logger = logging.getLogger(__name__)

_FENCE_PATTERN = re.compile(
    r"^```(?:json)?\s*\n?(.*?)\n?```\s*$",
    re.DOTALL | re.IGNORECASE,
)


@dataclass
class JsonExtractDiagnostics:
    """Internal parse diagnostics — never sent to API clients."""

    json_error_type: str | None = None
    json_error_position: int | None = None
    json_error_message: str | None = None
    raw_chars: int = 0
    stop_reason: str | None = None
    recovery_attempted: bool = False
    recovery_succeeded: bool = False
    recovery_mode: str | None = None


@dataclass
class JsonExtractResult:
    payload: dict[str, Any]
    recovered: bool = False
    diagnostics: JsonExtractDiagnostics = field(default_factory=JsonExtractDiagnostics)


def _diagnostics_from_decode_error(
    exc: json.JSONDecodeError,
    *,
    raw_chars: int,
) -> JsonExtractDiagnostics:
    return JsonExtractDiagnostics(
        json_error_type=type(exc).__name__,
        json_error_position=exc.pos,
        json_error_message=exc.msg,
        raw_chars=raw_chars,
    )


def _parse_object(candidate: str) -> dict[str, Any]:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        err = ClaudeJsonError("Invalid JSON in Claude response")
        err.diagnostics = _diagnostics_from_decode_error(exc, raw_chars=len(candidate))
        raise err from exc

    if isinstance(parsed, list):
        raise ClaudeJsonError("Expected JSON object, got array")
    if not isinstance(parsed, dict):
        raise ClaudeJsonError("Expected JSON object")
    return parsed


def _scan_balanced_objects(text: str) -> list[tuple[int, int]]:
    """Return (start, end_exclusive) spans of complete top-level `{...}` objects.

    String-aware: braces inside JSON strings (and escaped quotes) are ignored.
    Does not invent missing closers — incomplete nests are skipped.
    """
    spans: list[tuple[int, int]] = []
    depth = 0
    start = -1
    in_string = False
    escape = False
    i = 0
    length = len(text)
    while i < length:
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            i += 1
            continue

        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}":
            if depth == 0:
                i += 1
                continue
            depth -= 1
            if depth == 0 and start >= 0:
                spans.append((start, i + 1))
                start = -1
        i += 1

    return spans


def _try_fence(stripped: str) -> dict[str, Any] | None:
    fence_match = _FENCE_PATTERN.match(stripped)
    if not fence_match:
        return None
    inner = fence_match.group(1).strip()
    if not inner:
        return None
    return _parse_object(inner)


def _recover_via_balanced_scan(stripped: str) -> tuple[dict[str, Any], str]:
    """Find exactly one complete top-level object via brace scanner."""
    spans = _scan_balanced_objects(stripped)
    if not spans:
        raise ClaudeJsonError("Invalid JSON in Claude response")
    if len(spans) > 1:
        raise ClaudeJsonError("Ambiguous JSON: multiple valid object candidates")

    start, end = spans[0]
    candidate = stripped[start:end]
    payload = _parse_object(candidate)

    leading = stripped[:start].strip()
    trailing = stripped[end:].strip()
    if leading and trailing:
        mode = "preamble_and_trailing"
    elif leading:
        mode = "preamble"
    elif trailing:
        mode = "trailing"
    else:
        mode = "balanced_scan"
    return payload, mode


def extract_json_object_with_meta(
    raw_text: str,
    *,
    stop_reason: str | None = None,
) -> JsonExtractResult:
    """Extract exactly one JSON object, with safe wrapper recovery.

    Order:
    1. Pure object / whole-string fence (strict).
    2. Balanced-scan recovery for preamble/trailing wrappers.
    """
    diagnostics = JsonExtractDiagnostics(
        raw_chars=len(raw_text) if raw_text else 0,
        stop_reason=stop_reason,
    )

    if not raw_text or not raw_text.strip():
        raise ClaudeJsonError("Empty Claude response")

    stripped = raw_text.strip()

    # Fast-fail: top-level JSON array is never a menu object.
    if stripped.startswith("["):
        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError as exc:
            err = ClaudeJsonError("Invalid JSON in Claude response")
            err.diagnostics = _diagnostics_from_decode_error(exc, raw_chars=len(raw_text))
            raise err from exc
        if isinstance(parsed, list):
            raise ClaudeJsonError("Expected JSON object, got array")
        raise ClaudeJsonError("Expected JSON object")

    # 1a. Pure JSON object (entire string).
    if stripped.startswith("{"):
        try:
            payload = _parse_object(stripped)
            return JsonExtractResult(payload=payload, recovered=False, diagnostics=diagnostics)
        except ClaudeJsonError as exc:
            if getattr(exc, "diagnostics", None) is not None:
                diagnostics = exc.diagnostics
                diagnostics.stop_reason = stop_reason
                diagnostics.raw_chars = len(raw_text)
            # Fall through to recovery — may be preamble-free but trailing prose,
            # or genuinely malformed (recovery will also fail).

    # 1b. Whole-string fenced block.
    try:
        fenced = _try_fence(stripped)
        if fenced is not None:
            return JsonExtractResult(
                payload=fenced,
                recovered=False,
                diagnostics=diagnostics,
            )
    except ClaudeJsonError as exc:
        if getattr(exc, "diagnostics", None) is not None:
            diagnostics = exc.diagnostics
            diagnostics.stop_reason = stop_reason
            diagnostics.raw_chars = len(raw_text)

    # 2. Safe recovery via string-aware balanced scan.
    diagnostics.recovery_attempted = True
    try:
        payload, mode = _recover_via_balanced_scan(stripped)
        diagnostics.recovery_succeeded = True
        diagnostics.recovery_mode = mode
        return JsonExtractResult(
            payload=payload,
            recovered=True,
            diagnostics=diagnostics,
        )
    except ClaudeJsonError as exc:
        if getattr(exc, "diagnostics", None) is not None:
            failed = exc.diagnostics
            failed.recovery_attempted = True
            failed.recovery_succeeded = False
            failed.stop_reason = stop_reason
            failed.raw_chars = len(raw_text)
            exc.diagnostics = failed
        else:
            diagnostics.recovery_attempted = True
            diagnostics.recovery_succeeded = False
            exc.diagnostics = diagnostics
        raise


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """Extracts exactly one JSON object from Claude text (compat wrapper)."""
    return extract_json_object_with_meta(raw_text).payload
