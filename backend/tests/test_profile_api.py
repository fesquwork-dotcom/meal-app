"""API tests for explicit profile persistence and revisions."""

from __future__ import annotations

import asyncio

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from tests.profile_test_helpers import VALID_PROFILE_BODY, save_profile


@pytest.fixture
def client():
    return TestClient(main.app)


@pytest.fixture(autouse=True)
def _configure_auth_and_db(tmp_path, monkeypatch):
    db_path = tmp_path / "profile-api.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)


def test_get_missing_profile_revision_zero(client):
    response = client.get("/api/profile")
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 0
    assert body["profile"]["user_id"] == 42


def test_put_create_expected_zero_revision_one(client):
    response = save_profile(client, expected_revision=0)
    assert response.status_code == 200
    body = response.json()
    assert body["revision"] == 1
    assert body["profile"]["proteins"] == ["any"]


def test_put_update_increments_revision(client):
    save_profile(client, expected_revision=0)
    response = save_profile(
        client,
        expected_revision=1,
        days=4,
        proteins=["chicken"],
    )
    assert response.status_code == 200
    assert response.json()["revision"] == 2
    assert response.json()["profile"]["days"] == 4


def test_legacy_profile_limits_are_clamped_on_read(client):
    asyncio.run(
        database.save_profile(
            42,
            {
                **VALID_PROFILE_BODY,
                "days": 14,
                "budget": 80_000,
            },
        )
    )
    body = client.get("/api/profile").json()
    assert body["profile"]["days"] == 7
    assert body["profile"]["budget"] == 50_000


def test_old_client_intolerance_is_accepted_but_new_data_is_saved_as_allergy(client):
    response = client.put(
        "/api/profile",
        json={
            **VALID_PROFILE_BODY,
            "expected_revision": 0,
            "dietary_constraints": [
                {"kind": "intolerance", "value": "молоко"},
            ],
        },
    )
    assert response.status_code == 200
    constraints = response.json()["profile"]["dietary_constraints"]
    assert len(constraints) == 1
    assert constraints[0]["kind"] == "allergy"
    assert constraints[0]["value"] == "молоко"


def test_stale_put_returns_conflict(client):
    save_profile(client, expected_revision=0)
    save_profile(client, expected_revision=1, days=4)
    response = client.put(
        "/api/profile",
        json={**VALID_PROFILE_BODY, "expected_revision": 1, "days": 6},
    )
    assert response.status_code == 409
    body = response.json()
    assert body["code"] == "PROFILE_STALE"
    assert body["details"]["current_revision"] == 2
    assert body["details"]["current_profile"]["days"] == 4


def test_invalid_profile_does_not_increment_revision(client):
    save_profile(client, expected_revision=0)
    response = client.put(
        "/api/profile",
        json={
            **VALID_PROFILE_BODY,
            "expected_revision": 1,
            "proteins": [],
        },
    )
    assert response.status_code == 422
    current = client.get("/api/profile").json()
    assert current["revision"] == 1


def test_put_empty_proteins_incomplete(client):
    response = save_profile(client, expected_revision=0, proteins=[])
    assert response.status_code == 422
    assert response.json()["code"] == "PROFILE_PROTEIN_REQUIRED"


def test_put_any_with_specific_invalid(client):
    response = save_profile(client, expected_revision=0, proteins=["any", "fish"])
    assert response.status_code == 422
    assert response.json()["code"] == "PROFILE_ANY_WITH_SPECIFIC_PROTEINS"
