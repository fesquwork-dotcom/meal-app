"""Tests for memory signal promotion into profile preferences (Sprint 5.21)."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from dietary_constraints import DietaryConstraintKind, new_constraint_id
from memory.promotion_merge import apply_promotion_merge
from memory.promotion_service import MemoryPromotionService
from memory.service import MemoryService
from shopping.normalization import canonical_ingredient_name
from strategy.memory_context import build_strategy_memory_context
from strategy.effective_exclusions import build_profile_exclusions
from strategy.context import ProfileContext
from tests.profile_test_helpers import save_profile

NOW = datetime(2026, 7, 12, 12, 0, 0, tzinfo=timezone.utc)


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "memory-promotion.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _seed_avoid_signal(
    *,
    user_id: int = 42,
    ingredient: str = "гречка",
    key: str = "k1",
    repeat: int = 3,
) -> None:
    service = MemoryService()
    for index in range(repeat):
        asyncio.run(
            service.record_meal_replaced(
                user_id=user_id,
                strategy_id="s1",
                meal_id=f"day{index}_dinner",
                recipe_id="r1",
                reason_code="dislike_ingredient",
                target_ingredient=ingredient,
                event_key=f"{key}-{index}",
                now=NOW,
            )
        )


def _confirm_signal(client) -> str:
    signal_id = client.get("/api/memory/signals").json()["signals"][0]["id"]
    response = client.post(f"/api/memory/signals/{signal_id}/confirm")
    assert response.status_code == 200
    return signal_id


def _profile_revision(client) -> int:
    return client.get("/api/profile").json()["revision"]


def _promote(client, signal_id: str, expected_revision: int):
    return client.post(
        f"/api/memory/signals/{signal_id}/promote",
        json={"expected_profile_revision": expected_revision},
    )


def _ensure_profile(client, revision: int = 0):
    response = save_profile(client, expected_revision=revision)
    assert response.status_code == 200, response.text
    return response.json()


# --- Eligibility ---


def test_confirmed_avoid_is_promotable(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    revision = _profile_revision(client)

    response = _promote(client, signal_id, revision)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "promoted"
    assert body["signal_status"] == "promoted"
    assert body["profile_revision"] == revision + 1
    constraints = body["profile"]["dietary_constraints"]
    assert len(constraints) == 1
    assert constraints[0]["kind"] == "preference"
    assert constraints[0]["canonical_value"] == canonical_ingredient_name("гречка")
    assert client.get("/api/memory/signals").json() == {"signals": []}


def test_observed_avoid_rejected(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=1)
    signal_id = client.get("/api/memory/signals").json()["signals"][0]["id"]
    revision = _profile_revision(client)

    response = _promote(client, signal_id, revision)
    assert response.status_code == 422
    assert response.json()["code"] == "MEMORY_SIGNAL_NOT_CONFIRMED"


def test_dismissed_signal_rejected(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    assert client.delete(f"/api/memory/signals/{signal_id}").status_code == 200

    response = _promote(client, signal_id, _profile_revision(client))
    assert response.status_code == 422
    assert response.json()["code"] == "MEMORY_SIGNAL_NOT_PROMOTABLE"


def test_prefer_faster_promoted(client):
    _ensure_profile(client)
    asyncio.run(
        MemoryService().record_meal_replaced(
            user_id=42,
            strategy_id="s1",
            meal_id="day1_dinner",
            recipe_id="r1",
            reason_code="faster",
            target_ingredient=None,
            event_key="faster-1",
            now=NOW,
        )
    )
    signal_id = _confirm_signal(client)
    revision = _profile_revision(client)
    response = _promote(client, signal_id, revision)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "promoted"
    assert body["profile"]["cooking_preferences"]["prefer_faster_meals"] is True
    assert client.get("/api/memory/signals").json() == {"signals": []}


def test_foreign_signal_returns_404(client, monkeypatch):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 99)
    response = _promote(client, signal_id, 1)
    assert response.status_code == 404


def test_unknown_signal_returns_404(client):
    _ensure_profile(client)
    response = _promote(client, "missing-signal", 1)
    assert response.status_code == 404


# --- Profile integration ---


def test_promotion_increments_revision_once(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    revision = _profile_revision(client)

    response = _promote(client, signal_id, revision)
    assert response.status_code == 200
    assert response.json()["profile_revision"] == revision + 1


def test_stale_revision_rejected(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)

    response = _promote(client, signal_id, 0)
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "MEMORY_PROMOTION_PROFILE_STALE"
    assert body["details"]["current_revision"] == 1


def test_no_profile_mutation_on_failure(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    before = client.get("/api/profile").json()

    _promote(client, signal_id, 0)
    after = client.get("/api/profile").json()
    assert after["revision"] == before["revision"]
    assert after["profile"]["dietary_constraints"] == []


# --- Duplicate handling ---


def test_existing_preference_no_duplicate(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    save_profile(
        client,
        expected_revision=1,
        dietary_constraints=[
            {
                "kind": "preference",
                "value": "гречка",
            }
        ],
    )
    constraint_id = client.get("/api/profile").json()["profile"]["dietary_constraints"][0]["id"]
    revision = _profile_revision(client)

    response = _promote(client, signal_id, revision)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "already_promoted"
    assert body["profile_revision"] == revision
    assert body["constraint_id"] == constraint_id
    assert len(body["profile"]["dietary_constraints"]) == 1


def test_existing_allergy_already_covered(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    allergy_id = new_constraint_id()
    save_profile(
        client,
        expected_revision=1,
        dietary_constraints=[
            {
                "id": allergy_id,
                "kind": "allergy",
                "value": "гречка",
            }
        ],
    )
    revision = _profile_revision(client)

    response = _promote(client, signal_id, revision)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "already_covered"
    assert body["profile_revision"] == revision
    assert len(body["profile"]["dietary_constraints"]) == 1
    assert body["profile"]["dietary_constraints"][0]["kind"] == "allergy"
    assert client.get("/api/memory/signals").json() == {"signals": []}


def test_existing_intolerance_already_covered(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    save_profile(
        client,
        expected_revision=1,
        dietary_constraints=[
            {
                "id": new_constraint_id(),
                "kind": "intolerance",
                "value": "гречка",
            }
        ],
    )

    response = _promote(client, signal_id, _profile_revision(client))
    assert response.status_code == 200
    assert response.json()["status"] == "already_covered"


def test_repeated_promotion_idempotent(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    revision = _profile_revision(client)

    first = _promote(client, signal_id, revision)
    assert first.status_code == 200
    second = _promote(client, signal_id, revision + 1)
    assert second.status_code == 200
    assert second.json()["status"] == "already_promoted"
    assert second.json()["profile_revision"] == revision + 1


# --- Legacy handling ---


def test_matching_legacy_converts_to_preference(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    save_profile(client, expected_revision=1, legacy_allergies=["гречка"])
    revision = _profile_revision(client)

    response = _promote(client, signal_id, revision)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "promoted"
    profile = body["profile"]
    assert profile["dietary_constraints"][0]["kind"] == "preference"
    assert profile["allergies"] == "нет"


# --- Strategy integration ---


def test_promoted_signal_absent_from_memory_context(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    revision = _profile_revision(client)
    _promote(client, signal_id, revision)

    confirmed = asyncio.run(MemoryService().get_confirmed_signals(42))
    context = build_strategy_memory_context(confirmed)
    assert context.avoided_ingredients == ()


def test_profile_preference_in_effective_exclusions(client):
    _ensure_profile(client)
    _seed_avoid_signal(repeat=3)
    signal_id = _confirm_signal(client)
    revision = _profile_revision(client)
    promoted = _promote(client, signal_id, revision).json()
    profile = promoted["profile"]
    context = ProfileContext.from_profile(profile)
    exclusions = build_profile_exclusions(context)
    assert any(item.source == "profile_preference" for item in exclusions)


# --- Merge unit tests ---


def test_merge_assigns_memory_source():
    profile = {"allergies": "нет", "dietary_constraints": []}
    merge = apply_promotion_merge(
        profile,
        canonical_target=canonical_ingredient_name("гречка"),
        display_label="Гречка",
    )
    assert merge.outcome == "promoted"
    assert merge.constraints[0].source == "memory"


def test_merge_canonical_alias_no_duplicate():
    existing_id = new_constraint_id()
    canonical = canonical_ingredient_name("гречневая крупа")
    profile = {
        "allergies": "нет",
        "dietary_constraints": [
            {
                "id": existing_id,
                "kind": DietaryConstraintKind.PREFERENCE.value,
                "value": "гречка",
                "canonical_value": canonical,
            }
        ],
    }
    merge = apply_promotion_merge(
        profile,
        canonical_target=canonical,
        display_label="гречка",
    )
    assert merge.outcome == "already_promoted"
    assert merge.constraint_id == existing_id
    assert merge.profile_changed is False


# --- OpenAPI / request contract ---


def test_promote_request_schema(client):
    openapi = main.app.openapi()
    schema = openapi["components"]["schemas"]["PromoteMemorySignalRequest"]
    assert set(schema["properties"]) == {"expected_profile_revision"}
    assert schema.get("additionalProperties") is False
    assert schema["required"] == ["expected_profile_revision"]


def test_promote_endpoint_exists(client):
    paths = main.app.openapi()["paths"]
    assert "/api/memory/signals/{signal_id}/promote" in paths
    assert "post" in paths["/api/memory/signals/{signal_id}/promote"]
