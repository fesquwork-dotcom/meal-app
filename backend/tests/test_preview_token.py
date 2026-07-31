"""Unit tests for signed strategy preview tokens."""

from __future__ import annotations

import base64
import json

import pytest

import config
from strategy.behavior_context import StrategyBehaviorContext
from strategy.memory_context import StrategyMemoryContext
from strategy.preview_token import (
    PreviewTokenError,
    TOKEN_VERSION,
    issue_preview_token,
    verify_preview_token,
)


@pytest.fixture(autouse=True)
def _configure_secret(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "STRATEGY_PREVIEW_SECRET", "")


PROFILE = {
    "goal": "home",
    "days": 3,
    "budget": 3000,
    "proteins": ["any"],
    "cooktime": "medium",
    "allergies": "нет",
    "store": "any",
    "persons": 2,
    "meal_types": ["breakfast", "lunch", "dinner"],
    "meals_per_day": 3,
}
PROFILE_REVISION = 1
PLAN_START_DATE = "2026-07-13"
MEMORY = StrategyMemoryContext.empty()
BEHAVIOR = StrategyBehaviorContext.empty()
NOW = 1_700_000_000


def _issue(**kwargs):
    params = {
        "user_id": 42,
        "profile": PROFILE,
        "profile_revision": PROFILE_REVISION,
        "plan_start_date": PLAN_START_DATE,
        "memory_context": MEMORY,
        "behavior_context": BEHAVIOR,
        "now": NOW,
    }
    params.update(kwargs)
    return issue_preview_token(**params)


def test_issue_and_verify_valid_token():
    token, expires_at = _issue()
    assert expires_at == NOW + config.PREVIEW_TOKEN_TTL_SECONDS
    verified = verify_preview_token(
        token,
        user_id=42,
        profile=PROFILE,
        profile_revision=PROFILE_REVISION,
        memory_context=MEMORY,
        behavior_context=BEHAVIOR,
        now=NOW,
    )
    assert verified.payload.user_id == 42
    assert verified.payload.plan_start_date == PLAN_START_DATE
    assert verified.payload.version == TOKEN_VERSION


def test_changed_payload_invalid_signature():
    token, _ = _issue()
    payload_b64, sig = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    payload["ph"] = "deadbeef" * 4
    tampered_payload = base64.urlsafe_b64encode(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    tampered = f"{tampered_payload}.{sig}"
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            tampered,
            user_id=42,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_INVALID"


def test_changed_signature_invalid():
    token, _ = _issue()
    payload_b64, _ = token.split(".")
    tampered = f"{payload_b64}.{'a' * 43}"
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            tampered,
            user_id=42,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_INVALID"


def test_wrong_secret_invalid(monkeypatch):
    token, _ = _issue()
    monkeypatch.setattr(config, "STRATEGY_PREVIEW_SECRET", "other-secret")
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            token,
            user_id=42,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_INVALID"


def test_expired_token():
    token, _ = _issue()
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            token,
            user_id=42,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW + config.PREVIEW_TOKEN_TTL_SECONDS + 1,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_EXPIRED"


def test_future_issued_at_outside_tolerance():
    token, _ = _issue(now=NOW + 120)
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            token,
            user_id=42,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_INVALID"


def test_wrong_user():
    token, _ = _issue()
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            token,
            user_id=99,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_INVALID"


def test_wrong_profile_hash():
    token, _ = _issue()
    changed = {**PROFILE, "days": 5}
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            token,
            user_id=42,
            profile=changed,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_STALE_PROFILE"


def test_wrong_memory_hash():
    token, _ = _issue(memory_unavailable=True)
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            token,
            user_id=42,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            memory_unavailable=False,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_STALE_MEMORY"


def test_version_mismatch(monkeypatch):
    import strategy.versions as versions

    token, _ = _issue()
    monkeypatch.setattr(versions, "STRATEGY_RULES_VERSION", versions.STRATEGY_RULES_VERSION + 1)
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            token,
            user_id=42,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_VERSION_MISMATCH"


def test_token_v2_rejected():
    token, _ = _issue()
    payload_b64, _ = token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(payload_b64 + "=="))
    payload["v"] = 2
    from strategy.preview_token import _b64url_encode, _canonical_json, _sign

    payload_bytes = _canonical_json(payload)
    v2_token = f"{_b64url_encode(payload_bytes)}.{_sign(payload_bytes, config.get_strategy_preview_secret())}"
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            v2_token,
            user_id=42,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_VERSION_MISMATCH"


def test_malformed_token():
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            "not-a-token",
            user_id=42,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_INVALID"


def test_oversized_token():
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            "a" * 3000,
            user_id=42,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_INVALID"


def test_wrong_profile_revision():
    token, _ = issue_preview_token(
        user_id=42,
        profile=PROFILE,
        profile_revision=1,
        plan_start_date=PLAN_START_DATE,
        memory_context=MEMORY,
        behavior_context=BEHAVIOR,
        now=NOW,
    )
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            token,
            user_id=42,
            profile=PROFILE,
            profile_revision=2,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert exc.value.code == "STRATEGY_PREVIEW_STALE_PROFILE"


def test_secret_not_exposed_in_errors():
    token, _ = _issue()
    with pytest.raises(PreviewTokenError) as exc:
        verify_preview_token(
            token,
            user_id=99,
            profile=PROFILE,
            profile_revision=PROFILE_REVISION,
            memory_context=MEMORY,
        behavior_context=BEHAVIOR,
            now=NOW,
        )
    assert config.get_strategy_preview_secret() not in str(exc.value)
