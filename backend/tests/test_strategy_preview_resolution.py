"""Tests for conflict resolution and preview token validation."""

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
from tests.profile_test_helpers import generate_with_token, issue_preview_token, preview_strategy, save_profile


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _configure_auth_and_db(tmp_path, monkeypatch):
    db_path = tmp_path / "resolution-api.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


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


def test_stale_token_blocks_generation_without_claude(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)
    save_profile(client, expected_revision=1, cooktime="fast")

    generate_calls = 0

    async def fake_generate_menu(**_kwargs):
        nonlocal generate_calls
        generate_calls += 1
        return {"days": []}

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = generate_with_token(client, token)
    assert response.status_code == 409
    assert generate_calls == 0


def test_valid_token_allows_generation(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client, plan_start_date="2026-07-13")

    async def fake_generate_menu(**kwargs):
        from tests.menu_fixtures import build_valid_menu_dict

        menu = build_valid_menu_dict(days=kwargs["days"])
        start = kwargs.get("plan_start_date")
        menu["plan_start_date"] = start.isoformat()
        return menu

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = generate_with_token(client, token)
    assert response.status_code == 200
    assert response.json()["plan_start_date"] == "2026-07-13"


def test_token_stale_after_profile_save(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)

    save_profile(client, expected_revision=1, days=4)

    generate_calls = 0

    async def fake_generate_menu(**_kwargs):
        nonlocal generate_calls
        generate_calls += 1
        return {}

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    response = generate_with_token(client, token)
    assert response.status_code == 409
    assert generate_calls == 0


def test_generation_without_token_always_428(client, monkeypatch):
    async def fake_generate_menu(**kwargs):
        from tests.menu_fixtures import build_valid_menu_dict

        menu = build_valid_menu_dict(days=kwargs["days"])
        return menu

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    response = client.post(
        "/api/generate-menu",
        json={"days": 3, "budget": 3000, "proteins": ["any"]},
    )
    assert response.status_code == 422


def test_remove_last_protein_requires_input_without_save(client):
    asyncio.run(_seed_fish_avoid())
    save_profile(client, expected_revision=0, proteins=["fish"])
    preview = preview_strategy(client).json()
    conflict = preview["conflicts"][0]

    response = client.post(
        "/api/strategy/resolve-conflict",
        json={
            "preview_token": preview["preview_token"],
            "conflict_id": conflict["conflict_id"],
            "action": "remove_profile_protein",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "requires_input"
    assert body["code"] == "PROFILE_REQUIRES_PROTEIN_SELECTION"
    assert body["field"] == "proteins"

    profile = client.get("/api/profile").json()
    assert profile["profile"]["proteins"] == ["fish"]
    assert profile["revision"] == 1
