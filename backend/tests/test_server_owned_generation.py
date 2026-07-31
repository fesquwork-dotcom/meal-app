"""Server-owned generation context tests (Sprint 5.18)."""

from __future__ import annotations

import asyncio
from datetime import date

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from tests.profile_test_helpers import (
    generate_with_token,
    issue_preview_token,
    preview_strategy,
    save_profile,
)


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "server-owned.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    asyncio.run(database.init_db())
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    return TestClient(main.app)


def test_profile_revision_unchanged_after_generation(client, monkeypatch):
    save_profile(client, expected_revision=0)
    before = client.get("/api/profile").json()
    token = issue_preview_token(client, plan_start_date="2026-07-13")

    async def fake_generate_menu(**kwargs):
        from tests.menu_fixtures import build_valid_menu_dict

        menu = build_valid_menu_dict(days=kwargs["days"])
        menu["plan_start_date"] = kwargs["plan_start_date"].isoformat()
        return menu

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    response = generate_with_token(client, token)
    assert response.status_code == 200

    after = client.get("/api/profile").json()
    assert after["revision"] == before["revision"]
    assert after["updated_at"] == before["updated_at"]


def test_generate_uses_plan_date_from_token_not_request(client, monkeypatch):
    save_profile(client, expected_revision=0)
    token = issue_preview_token(client, plan_start_date="2026-07-13")
    captured: dict[str, object] = {}

    async def fake_generate_menu(**kwargs):
        captured["plan_start_date"] = kwargs.get("plan_start_date")
        from tests.menu_fixtures import build_valid_menu_dict

        menu = build_valid_menu_dict(days=kwargs["days"])
        menu["plan_start_date"] = kwargs["plan_start_date"].isoformat()
        return menu

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    response = generate_with_token(client, token)
    assert response.status_code == 200
    assert captured["plan_start_date"] == date(2026, 7, 13)


def test_preview_binds_plan_start_date_in_token(client, monkeypatch):
    save_profile(client, expected_revision=0)
    response = preview_strategy(client, plan_start_date="2026-07-13")
    assert response.status_code == 200
    token = response.json()["preview_token"]

    captured: dict[str, object] = {}

    async def fake_generate_menu(**kwargs):
        captured["plan_start_date"] = kwargs.get("plan_start_date")
        from tests.menu_fixtures import build_valid_menu_dict

        menu = build_valid_menu_dict(days=kwargs["days"])
        menu["plan_start_date"] = kwargs["plan_start_date"].isoformat()
        return menu

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    response = generate_with_token(client, token)
    assert response.status_code == 200
    assert captured["plan_start_date"] == date(2026, 7, 13)
    assert response.json()["plan_start_date"] == "2026-07-13"


def test_request_profile_cannot_override_persisted_profile(client, monkeypatch):
    save_profile(client, expected_revision=0, days=3)
    response = preview_strategy(client)
    assert response.status_code == 200
    assert response.json()["strategy"]["days"] == 3

    token = response.json()["preview_token"]
    captured: dict[str, object] = {}

    async def fake_generate_menu(**kwargs):
        captured["days"] = kwargs.get("days")
        from tests.menu_fixtures import build_valid_menu_dict

        menu = build_valid_menu_dict(days=kwargs["days"])
        menu["plan_start_date"] = kwargs["plan_start_date"].isoformat()
        return menu

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    response = generate_with_token(client, token)
    assert response.status_code == 200
    assert captured["days"] == 3
