"""Privacy and architectural isolation for Learned Preferences."""

import asyncio
import json
import pathlib

import aiosqlite
import pytest
from fastapi.testclient import TestClient

import config
import database
import main

FORBIDDEN_KEYS = {
    "strategy_id",
    "decision_id",
    "memory_event_id",
    "event_id",
    "behavior_id",
    "meal_id",
    "profile_revision",
    "user_id",
    "source_strategy_id",
    "decision_key",
    "evidence_json",
    "preference_json",
}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "lp-privacy.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _seed_accepted_recommendation():
    async def _run():
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_learning_recommendations_table(db)
            await db.execute(
                """
                INSERT INTO learning_recommendations (
                    id, user_id, recommendation_key, recommendation_type,
                    decision_key, status, confidence, rule_version,
                    source_strategy_id, profile_patch_json,
                    created_at, updated_at, accepted_at, dismissed_at, expired_at
                ) VALUES (?, 42, ?, ?, ?, 'accepted', 'strong', 1, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    "rec-familiar",
                    "v1:profile_enable_prefer_familiar_meals",
                    "profile_enable_prefer_familiar_meals",
                    "planning.prefer_familiar_meals",
                    "secret-strategy-123",
                    '{"planning_preferences": {"prefer_familiar_meals": true}}',
                    "2026-07-10T00:00:00+00:00",
                    "2026-07-10T00:00:00+00:00",
                    "2026-07-11T00:00:00+00:00",
                ),
            )
            await db.commit()

    asyncio.run(_run())


def _all_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _all_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_keys(item)


def test_api_never_exposes_internal_identifiers(client):
    _seed_accepted_recommendation()
    body = client.post("/api/learned-preferences/v1:prefer_familiar_meals/accept").json()
    assert set(_all_keys(body)).isdisjoint(FORBIDDEN_KEYS)


def test_texts_never_leak_source_ids(client):
    _seed_accepted_recommendation()
    text = json.dumps(client.get("/api/learned-preferences").json(), ensure_ascii=False)
    lowered = text.lower()
    for forbidden in ("secret-strategy", "strategy_", "decision_key", "s1", "event_"):
        assert forbidden not in lowered


def test_non_decision_core_layers_do_not_import_learned_preferences():
    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    for package in ("learning", "strategy", "trends", "plan_delta", "insights"):
        for path in (backend_dir / package).glob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "from learned_preferences" not in source, path
            assert "import learned_preferences" not in source, path


def test_decision_domain_import_is_confined_to_context_builder():
    decision_dir = pathlib.Path(__file__).resolve().parents[1] / "decision"
    for path in decision_dir.glob("*.py"):
        if path.name == "learned_preferences_context.py":
            continue
        source = path.read_text(encoding="utf-8")
        assert "from learned_preferences" not in source, path
        assert "import learned_preferences" not in source, path


def test_learned_preferences_do_not_import_decision_engine():
    package_dir = pathlib.Path(__file__).resolve().parents[1] / "learned_preferences"
    for path in package_dir.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        for forbidden in ("import anthropic", "import openai", "datetime.now("):
            # Purity/PII guards for the read/write layer, excluding the
            # repository's timestamp helper.
            if path.name == "repository.py" and forbidden == "datetime.now(":
                continue
            assert forbidden not in source, f"{path.name}: {forbidden}"


def test_replacement_and_menu_plan_paths_never_read_live_learned_preferences():
    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    paths = [
        backend_dir / "strategy" / "replacement_service.py",
        backend_dir / "strategy" / "replacement_context.py",
        backend_dir / "strategy" / "replacement_prompt.py",
        backend_dir / "menu_plan" / "service.py",
        backend_dir / "menu_plan" / "repository.py",
    ]
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "learned_preferences" not in source, path
        assert "LearnedPreference" not in source, path
