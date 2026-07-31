"""HMAC-signed stateless strategy preview tokens."""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Callable

import config
from strategy import versions
from strategy.fingerprint import (
    compute_behavior_hash,
    compute_learned_preferences_hash,
    compute_memory_hash,
    compute_profile_hash,
)
from decision.learned_preferences_context import (
    LEARNED_PREFERENCES_CONTEXT_VERSION,
    LearnedPreferencesContext,
)
from strategy.behavior_context import StrategyBehaviorContext
from strategy.memory_context import MEMORY_CONTEXT_VERSION, StrategyMemoryContext

TOKEN_VERSION = 5
MAX_TOKEN_LENGTH = 2048
MAX_PAYLOAD_BYTES = 1024
CLOCK_SKEW_SECONDS = 60

logger = logging.getLogger(__name__)

ClockFn = Callable[[], int]


@dataclass(frozen=True)
class PreviewTokenPayload:
    version: int
    user_id: int
    issued_at: int
    expires_at: int
    profile_hash: str
    memory_hash: str
    behavior_hash: str
    learned_preferences_hash: str
    rules_version: int
    preview_version: int
    memory_context_version: int
    memory_unavailable: bool
    behavior_unavailable: bool
    learned_preferences_context_version: int
    learned_preferences_unavailable: bool
    profile_revision: int
    plan_start_date: str
    nonce: str


@dataclass(frozen=True)
class VerifiedPreviewToken:
    payload: PreviewTokenPayload


@dataclass(frozen=True)
class PreviewTokenError(Exception):
    code: str
    message: str = "Preview token is invalid"

    def __str__(self) -> str:
        return self.message


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _canonical_json(payload: dict[str, object]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _payload_to_dict(payload: PreviewTokenPayload) -> dict[str, object]:
    return {
        "v": payload.version,
        "uid": payload.user_id,
        "iat": payload.issued_at,
        "exp": payload.expires_at,
        "ph": payload.profile_hash,
        "mh": payload.memory_hash,
        "bh": payload.behavior_hash,
        "lph": payload.learned_preferences_hash,
        "rv": payload.rules_version,
        "pv": payload.preview_version,
        "mcv": payload.memory_context_version,
        "mu": payload.memory_unavailable,
        "bu": payload.behavior_unavailable,
        "lcv": payload.learned_preferences_context_version,
        "lpu": payload.learned_preferences_unavailable,
        "pr": payload.profile_revision,
        "psd": payload.plan_start_date,
        "n": payload.nonce,
    }


def _payload_from_dict(data: dict[str, object]) -> PreviewTokenPayload:
    return PreviewTokenPayload(
        version=int(data["v"]),
        user_id=int(data["uid"]),
        issued_at=int(data["iat"]),
        expires_at=int(data["exp"]),
        profile_hash=str(data["ph"]),
        memory_hash=str(data["mh"]),
        behavior_hash=str(data.get("bh", "")),
        learned_preferences_hash=str(data.get("lph", "")),
        rules_version=int(data["rv"]),
        preview_version=int(data["pv"]),
        memory_context_version=int(data["mcv"]),
        memory_unavailable=bool(data["mu"]),
        behavior_unavailable=bool(data.get("bu", False)),
        learned_preferences_context_version=int(data.get("lcv", 0)),
        learned_preferences_unavailable=bool(data.get("lpu", False)),
        profile_revision=int(data["pr"]),
        plan_start_date=str(data["psd"]),
        nonce=str(data["n"]),
    )


def _sign(payload_bytes: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).digest()
    return _b64url_encode(digest)


def issue_preview_token(
    *,
    user_id: int,
    profile: dict[str, object],
    profile_revision: int,
    plan_start_date: str,
    memory_context: StrategyMemoryContext,
    behavior_context: StrategyBehaviorContext,
    learned_context: LearnedPreferencesContext | None = None,
    memory_unavailable: bool = False,
    behavior_unavailable: bool = False,
    learned_preferences_unavailable: bool = False,
    now: int | None = None,
    clock: ClockFn | None = None,
) -> tuple[str, int]:
    """Returns (token, expires_at_unix)."""
    secret = config.get_strategy_preview_secret()
    now_fn = clock or (lambda: int(time.time()))
    issued_at = now if now is not None else now_fn()
    expires_at = issued_at + config.PREVIEW_TOKEN_TTL_SECONDS
    effective_learned = learned_context or LearnedPreferencesContext.empty()
    payload = PreviewTokenPayload(
        version=TOKEN_VERSION,
        user_id=user_id,
        issued_at=issued_at,
        expires_at=expires_at,
        profile_hash=compute_profile_hash(profile),
        memory_hash=compute_memory_hash(memory_context, memory_unavailable=memory_unavailable),
        behavior_hash=compute_behavior_hash(
            behavior_context, behavior_unavailable=behavior_unavailable
        ),
        learned_preferences_hash=compute_learned_preferences_hash(
            effective_learned,
            unavailable=learned_preferences_unavailable,
        ),
        rules_version=versions.STRATEGY_RULES_VERSION,
        preview_version=versions.STRATEGY_PREVIEW_VERSION,
        memory_context_version=MEMORY_CONTEXT_VERSION,
        memory_unavailable=memory_unavailable,
        behavior_unavailable=behavior_unavailable,
        learned_preferences_context_version=LEARNED_PREFERENCES_CONTEXT_VERSION,
        learned_preferences_unavailable=learned_preferences_unavailable,
        profile_revision=profile_revision,
        plan_start_date=plan_start_date,
        nonce=secrets.token_hex(8),
    )
    payload_bytes = _canonical_json(_payload_to_dict(payload))
    token = f"{_b64url_encode(payload_bytes)}.{_sign(payload_bytes, secret)}"
    if len(token) > MAX_TOKEN_LENGTH:
        raise PreviewTokenError("STRATEGY_PREVIEW_INVALID", "Preview token is too large")
    return token, expires_at


def verify_preview_token(
    token: str,
    *,
    user_id: int,
    profile: dict[str, object],
    profile_revision: int,
    memory_context: StrategyMemoryContext,
    behavior_context: StrategyBehaviorContext,
    learned_context: LearnedPreferencesContext | None = None,
    memory_unavailable: bool = False,
    behavior_unavailable: bool = False,
    learned_preferences_unavailable: bool = False,
    now: int | None = None,
    clock: ClockFn | None = None,
) -> VerifiedPreviewToken:
    if not token or len(token) > MAX_TOKEN_LENGTH:
        raise PreviewTokenError("STRATEGY_PREVIEW_INVALID")

    parts = token.split(".")
    if len(parts) != 2 or not parts[0] or not parts[1]:
        raise PreviewTokenError("STRATEGY_PREVIEW_INVALID")

    try:
        payload_bytes = _b64url_decode(parts[0])
    except (ValueError, binascii.Error) as exc:
        raise PreviewTokenError("STRATEGY_PREVIEW_INVALID") from exc

    if len(payload_bytes) > MAX_PAYLOAD_BYTES:
        raise PreviewTokenError("STRATEGY_PREVIEW_INVALID")

    secret = config.get_strategy_preview_secret()
    expected_sig = _sign(payload_bytes, secret)
    if not hmac.compare_digest(expected_sig, parts[1]):
        raise PreviewTokenError("STRATEGY_PREVIEW_INVALID")

    try:
        parsed = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PreviewTokenError("STRATEGY_PREVIEW_INVALID") from exc

    if not isinstance(parsed, dict):
        raise PreviewTokenError("STRATEGY_PREVIEW_INVALID")

    try:
        payload = _payload_from_dict(parsed)
    except (KeyError, TypeError, ValueError) as exc:
        raise PreviewTokenError("STRATEGY_PREVIEW_INVALID") from exc

    now_fn = clock or (lambda: int(time.time()))
    current = now if now is not None else now_fn()

    if payload.version != TOKEN_VERSION:
        if payload.version in {2, 3, 4}:
            logger.info("token_legacy_rejected user_id=%s version=%s", user_id, payload.version)
        raise PreviewTokenError("STRATEGY_PREVIEW_VERSION_MISMATCH")

    if payload.user_id != user_id:
        raise PreviewTokenError("STRATEGY_PREVIEW_INVALID")

    if current > payload.expires_at:
        raise PreviewTokenError("STRATEGY_PREVIEW_EXPIRED")

    if payload.issued_at > current + CLOCK_SKEW_SECONDS:
        raise PreviewTokenError("STRATEGY_PREVIEW_INVALID")

    if payload.rules_version != versions.STRATEGY_RULES_VERSION:
        raise PreviewTokenError("STRATEGY_PREVIEW_VERSION_MISMATCH")

    if payload.preview_version != versions.STRATEGY_PREVIEW_VERSION:
        raise PreviewTokenError("STRATEGY_PREVIEW_VERSION_MISMATCH")

    if payload.memory_context_version != MEMORY_CONTEXT_VERSION:
        raise PreviewTokenError("STRATEGY_PREVIEW_VERSION_MISMATCH")
    if (
        payload.learned_preferences_context_version
        != LEARNED_PREFERENCES_CONTEXT_VERSION
    ):
        raise PreviewTokenError("STRATEGY_PREVIEW_VERSION_MISMATCH")

    if payload.profile_revision != profile_revision:
        raise PreviewTokenError("STRATEGY_PREVIEW_STALE_PROFILE")

    profile_hash = compute_profile_hash(profile)
    if payload.profile_hash != profile_hash:
        raise PreviewTokenError("STRATEGY_PREVIEW_STALE_PROFILE")

    memory_hash = compute_memory_hash(memory_context, memory_unavailable=memory_unavailable)
    if payload.memory_hash != memory_hash:
        raise PreviewTokenError("STRATEGY_PREVIEW_STALE_MEMORY")

    if payload.memory_unavailable != memory_unavailable:
        raise PreviewTokenError("STRATEGY_PREVIEW_STALE_MEMORY")

    behavior_hash = compute_behavior_hash(
        behavior_context, behavior_unavailable=behavior_unavailable
    )
    if payload.behavior_hash != behavior_hash:
        raise PreviewTokenError("STRATEGY_PREVIEW_STALE_BEHAVIOR")

    if payload.behavior_unavailable != behavior_unavailable:
        raise PreviewTokenError("STRATEGY_PREVIEW_STALE_BEHAVIOR")

    learned_hash = compute_learned_preferences_hash(
        learned_context or LearnedPreferencesContext.empty(),
        unavailable=learned_preferences_unavailable,
    )
    if payload.learned_preferences_hash != learned_hash:
        logger.info("learned_preferences_preview_stale")
        raise PreviewTokenError(
            "STRATEGY_PREVIEW_STALE_LEARNED_PREFERENCES"
        )
    if (
        payload.learned_preferences_unavailable
        != learned_preferences_unavailable
    ):
        logger.info("learned_preferences_preview_stale")
        raise PreviewTokenError(
            "STRATEGY_PREVIEW_STALE_LEARNED_PREFERENCES"
        )

    return VerifiedPreviewToken(payload=payload)
