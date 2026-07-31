import asyncio
from datetime import date

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from strategy.exceptions import StrategyPersistenceError
from strategy.repository import StrategyRepository
from strategy.service import StrategyService
from tests.menu_fixtures import build_valid_menu_dict
from tests.profile_test_helpers import generate_with_token, issue_preview_token, save_profile
from tests.strategy_fixtures import build_test_strategy


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_path = tmp_path / "strategy-pipeline.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(db_path))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def test_successful_generation_saves_strategy_and_returns_strategy_id(client, monkeypatch):
    captured_strategy = {}

    async def fake_generate_menu(**kwargs):
        captured_strategy["strategy"] = kwargs.get("strategy")
        menu = build_valid_menu_dict(days=kwargs["days"])
        if kwargs.get("plan_start_date"):
            menu["plan_start_date"] = kwargs["plan_start_date"].isoformat()
        return menu

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    save_profile(client, expected_revision=0)
    plan_start = date.today().isoformat()
    token = issue_preview_token(client, plan_start_date=plan_start)
    response = generate_with_token(client, token)

    assert response.status_code == 200
    body = response.json()
    assert body["strategy_id"]
    assert body["plan_start_date"] == plan_start

    current = client.get("/api/strategy/current").json()
    assert current["status"] == "active"
    assert current["strategy_id"] == body["strategy_id"]
    assert captured_strategy["strategy"] is not None
    assert current["strategy"]["days"] == captured_strategy["strategy"].days


def test_failed_generation_does_not_save_strategy(client, monkeypatch):
    from claude_exceptions import ClaudeJsonError

    async def failing_generate_menu(**_kwargs):
        raise ClaudeJsonError("bad json")

    monkeypatch.setattr(main, "generate_menu", failing_generate_menu)

    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)
    response = generate_with_token(client, token)
    assert response.status_code == 502

    current = client.get("/api/strategy/current").json()
    assert current["status"] == "none"


def test_new_generation_supersedes_previous(client, monkeypatch):
    async def fake_generate_menu(**kwargs):
        menu = build_valid_menu_dict(days=kwargs["days"])
        return menu

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)

    save_profile(client, expected_revision=0, days=3)
    first = generate_with_token(client, issue_preview_token(client)).json()
    save_profile(client, expected_revision=1, days=5)
    second = generate_with_token(client, issue_preview_token(client)).json()

    assert first["strategy_id"] != second["strategy_id"]

    current = client.get("/api/strategy/current").json()
    assert current["strategy_id"] == second["strategy_id"]


def test_db_error_after_generation_returns_503_without_strategy_id(client, monkeypatch):
    async def fake_generate_menu(**_kwargs):
        return build_valid_menu_dict(days=3)

    async def failing_save(*_args, **_kwargs):
        raise StrategyPersistenceError("db down")

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    monkeypatch.setattr(main._strategy_service, "save_active_strategy", failing_save)

    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)
    response = generate_with_token(client, token)

    assert response.status_code == 503
    assert "strategy_id" not in response.json()


def test_correction_retry_does_not_create_duplicate_strategies(client, monkeypatch):
    """Persistence runs once in main after a single successful generate_menu call."""
    save_calls = 0
    original_save = main._strategy_service.save_active_strategy

    async def counting_save(**kwargs):
        nonlocal save_calls
        save_calls += 1
        return await original_save(**kwargs)

    async def fake_generate_menu(**kwargs):
        return build_valid_menu_dict(days=kwargs["days"])

    monkeypatch.setattr(main, "generate_menu", fake_generate_menu)
    monkeypatch.setattr(main._strategy_service, "save_active_strategy", counting_save)

    save_profile(client, expected_revision=0)
    token = issue_preview_token(client)
    response = generate_with_token(client, token)

    assert response.status_code == 200
    assert save_calls == 1

    async def _count_active():
        async with aiosqlite.connect(config.DATABASE_PATH) as db:
            cursor = await db.execute(
                "SELECT COUNT(*) FROM weekly_strategies WHERE user_id = 42 AND status = 'active'"
            )
            return (await cursor.fetchone())[0]

    assert asyncio.run(_count_active()) == 1
