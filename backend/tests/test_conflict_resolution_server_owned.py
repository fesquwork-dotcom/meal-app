"""Server-owned conflict resolution API tests."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from memory.aggregation import SignalDraft
from memory.constants import ConfirmationSource, SignalStatus, SignalType
from memory.repository import MemoryRepository
from tests.profile_test_helpers import issue_preview_token, preview_strategy, save_profile


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "conflict-resolution.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    return TestClient(main.app)


async def _seed_fish_avoid() -> str:
    repo = MemoryRepository()
    await repo.upsert_signal(
        42,
        SignalDraft(
            signal_type=SignalType.AVOID_INGREDIENT.value,
            target_value="рыба",
            target_label="Рыба",
            status=SignalStatus.CONFIRMED.value,
            confidence=1.0,
            evidence_count=3,
            first_observed_at="2026-01-01T00:00:00+00:00",
            last_observed_at="2026-01-01T00:00:00+00:00",
            confirmation_source=ConfirmationSource.USER.value,
        ),
        "2026-01-01T00:00:00+00:00",
    )
    signal = await repo.get_signal(
        user_id=42,
        signal_type=SignalType.AVOID_INGREDIENT.value,
        target_value="рыба",
    )
    assert signal is not None
    return signal.id


def _resolve_payload(preview_token: str, conflict_id: str, action: str, **extra):
    return {
        "preview_token": preview_token,
        "conflict_id": conflict_id,
        "action": action,
        **extra,
    }


def test_valid_resolution_with_token_and_conflict_id(client):
    save_profile(client, expected_revision=0, proteins=["fish"])
    asyncio.run(_seed_fish_avoid())
    preview = preview_strategy(client).json()
    conflict = preview["conflicts"][0]

    response = client.post(
        "/api/strategy/resolve-conflict",
        json=_resolve_payload(
            preview["preview_token"],
            conflict["conflict_id"],
            "remove_profile_protein",
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "requires_input"
    assert body["code"] == "PROFILE_REQUIRES_PROTEIN_SELECTION"
    assert body["requires_new_preview"] is True


def test_extra_profile_fields_rejected(client):
    save_profile(client, expected_revision=0, proteins=["fish"])
    asyncio.run(_seed_fish_avoid())
    preview = preview_strategy(client).json()
    conflict = preview["conflicts"][0]

    response = client.post(
        "/api/strategy/resolve-conflict",
        json={
            **_resolve_payload(
                preview["preview_token"],
                conflict["conflict_id"],
                "remove_profile_protein",
            ),
            "proteins": ["any"],
            "days": 5,
        },
    )
    assert response.status_code == 422


def test_arbitrary_signal_id_rejected(client):
    save_profile(client, expected_revision=0, proteins=["fish"])
    asyncio.run(_seed_fish_avoid())
    preview = preview_strategy(client).json()
    conflict = preview["conflicts"][0]

    response = client.post(
        "/api/strategy/resolve-conflict",
        json={
            **_resolve_payload(
                preview["preview_token"],
                conflict["conflict_id"],
                "dismiss_memory_signal",
            ),
            "memory_signal_id": "foreign-signal",
        },
    )
    assert response.status_code == 422


def test_missing_preview_token_rejected(client):
    response = client.post(
        "/api/strategy/resolve-conflict",
        json={"conflict_id": "cfl_abc", "action": "dismiss_memory_signal"},
    )
    assert response.status_code == 422


def test_invalid_action_rejected(client):
    save_profile(client, expected_revision=0, proteins=["fish"])
    asyncio.run(_seed_fish_avoid())
    preview = preview_strategy(client).json()
    conflict = preview["conflicts"][0]

    response = client.post(
        "/api/strategy/resolve-conflict",
        json=_resolve_payload(
            preview["preview_token"],
            conflict["conflict_id"],
            "continue_with_warning",
        ),
    )
    assert response.status_code == 422


def test_stale_profile_blocks_resolution(client):
    save_profile(client, expected_revision=0, proteins=["fish"])
    asyncio.run(_seed_fish_avoid())
    preview = preview_strategy(client).json()
    conflict = preview["conflicts"][0]
    token = preview["preview_token"]

    save_profile(client, expected_revision=1, cooktime="fast")

    response = client.post(
        "/api/strategy/resolve-conflict",
        json=_resolve_payload(token, conflict["conflict_id"], "dismiss_memory_signal"),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "STRATEGY_PREVIEW_STALE_PROFILE"


def test_dismiss_memory_signal_resolves_without_profile_change(client):
    save_profile(client, expected_revision=0, proteins=["fish"])
    asyncio.run(_seed_fish_avoid())
    before_revision = client.get("/api/profile").json()["revision"]
    preview = preview_strategy(client).json()
    assert preview["status"] == "conflict"
    conflict = preview["conflicts"][0]

    response = client.post(
        "/api/strategy/resolve-conflict",
        json=_resolve_payload(
            preview["preview_token"],
            conflict["conflict_id"],
            "dismiss_memory_signal",
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved"
    assert body["profile_revision"] == before_revision
    assert body["requires_new_preview"] is True

    after = client.get("/api/profile").json()
    assert after["revision"] == before_revision
    assert after["profile"]["proteins"] == ["fish"]


def test_remove_protein_with_remaining_protein_succeeds(client, monkeypatch):
    from profile_validation import ProfileValidationResult

    monkeypatch.setattr(
        main,
        "validate_profile_for_generation",
        lambda _profile: ProfileValidationResult(status="valid"),
    )

    save_profile(client, expected_revision=0, proteins=["fish", "chicken"], allergies="нет")

    async def _set_contradictory_allergies():
        stored = await database.get_profile(42)
        assert stored is not None
        stored["allergies"] = "рыба"
        await database.save_profile_with_revision(42, stored, int(stored["revision"]))

    asyncio.run(_set_contradictory_allergies())

    preview = preview_strategy(client).json()
    assert preview["status"] == "conflict"
    conflict = preview["conflicts"][0]

    response = client.post(
        "/api/strategy/resolve-conflict",
        json=_resolve_payload(
            preview["preview_token"],
            conflict["conflict_id"],
            "remove_profile_protein",
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved"
    assert body["profile_revision"] == 3

    profile = client.get("/api/profile").json()
    assert profile["profile"]["proteins"] == ["chicken"]
    assert profile["revision"] == 3


def test_remove_profile_preference_succeeds(client, monkeypatch):
    from profile_validation import ProfileValidationResult

    monkeypatch.setattr(
        main,
        "validate_profile_payload",
        lambda _profile: ProfileValidationResult(status="valid"),
    )
    monkeypatch.setattr(
        main,
        "validate_profile_for_generation",
        lambda _profile: ProfileValidationResult(status="valid"),
    )

    save_profile(
        client,
        expected_revision=0,
        proteins=["fish", "chicken"],
        dietary_constraints=[
            {"kind": "preference", "value": "рыба"},
        ],
        legacy_allergies=[],
    )

    preview = preview_strategy(client).json()
    assert preview["status"] == "conflict"
    conflict = next(
        item for item in preview["conflicts"] if item["code"] == "PREFERRED_PROTEIN_EXCLUDED_BY_PROFILE_PREFERENCE"
    )

    response = client.post(
        "/api/strategy/resolve-conflict",
        json=_resolve_payload(
            preview["preview_token"],
            conflict["conflict_id"],
            "remove_profile_preference",
        ),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "resolved"

    profile = client.get("/api/profile").json()
    assert "рыба" not in [
        item["value"] for item in profile["profile"]["dietary_constraints"]
    ]
    assert profile["profile"]["proteins"] == ["fish", "chicken"]


def test_remove_profile_preference_rejected_for_legacy(client, monkeypatch):
    from profile_validation import ProfileValidationResult

    monkeypatch.setattr(
        main,
        "validate_profile_payload",
        lambda _profile: ProfileValidationResult(status="valid"),
    )
    monkeypatch.setattr(
        main,
        "validate_profile_for_generation",
        lambda _profile: ProfileValidationResult(status="valid"),
    )

    save_profile(
        client,
        expected_revision=0,
        proteins=["fish"],
        legacy_allergies=["рыба"],
    )

    preview = preview_strategy(client).json()
    assert preview["status"] == "conflict"
    conflict = preview["conflicts"][0]
    assert conflict["code"] == "PREFERRED_PROTEIN_BLOCKED_BY_LEGACY_CONSTRAINT"
    assert not any(
        opt["action"] == "remove_profile_preference" for opt in conflict["options"]
    )


def test_old_remove_profile_exclusion_action_rejected(client):
    save_profile(client, expected_revision=0, proteins=["fish"])
    preview = preview_strategy(client).json()
    if preview["status"] != "conflict":
        return
    response = client.post(
        "/api/strategy/resolve-conflict",
        json={
            "preview_token": preview["preview_token"],
            "conflict_id": preview["conflicts"][0]["conflict_id"],
            "action": "remove_profile_exclusion",
        },
    )
    assert response.status_code == 422
    save_profile(client, expected_revision=0, proteins=["fish"])
    asyncio.run(_seed_fish_avoid())
    preview = preview_strategy(client).json()

    response = client.post(
        "/api/strategy/resolve-conflict",
        json=_resolve_payload(
            preview["preview_token"],
            "cfl_deadbeefdead",
            "dismiss_memory_signal",
        ),
    )
    assert response.status_code == 409
    assert response.json()["code"] == "CONFLICT_NOT_FOUND"
