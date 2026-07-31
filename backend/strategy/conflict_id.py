"""Deterministic conflict identifiers for server-owned resolution."""

from __future__ import annotations

import hashlib
import json
import re

CONFLICT_ID_PATTERN = re.compile(r"^cfl_[a-f0-9]{12,32}$")
MAX_CONFLICT_ID_LENGTH = 40


def compute_conflict_id(
    *,
    code: str,
    field: str | None,
    canonical_value: str | None,
    memory_signal_id: str | None,
    profile_revision: int,
    preview_version: int,
) -> str:
    payload = {
        "c": code,
        "f": field or "",
        "v": canonical_value or "",
        "m": memory_signal_id or "",
        "pr": profile_revision,
        "pv": preview_version,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return f"cfl_{digest[:12]}"


def is_valid_conflict_id(value: str) -> bool:
    return bool(value) and len(value) <= MAX_CONFLICT_ID_LENGTH and bool(CONFLICT_ID_PATTERN.match(value))
