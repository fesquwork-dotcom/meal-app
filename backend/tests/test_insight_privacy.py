"""Recursive privacy and anti-hallucination checks for Insight API."""

import asyncio
import json

import pytest
from fastapi.testclient import TestClient

import config
import database
import main


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "insight-privacy.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())
    return TestClient(main.app)


def _all_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from _all_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from _all_keys(item)


def test_api_never_exposes_internal_identifiers_or_raw_values(client):
    body = client.get("/api/insights/summary").json()
    keys = set(_all_keys(body))
    forbidden = {
        "strategy_id",
        "menu_plan_id",
        "revision",
        "decision_context",
        "decision_context_json",
        "event_id",
        "event_key",
        "user_id",
        "value",
        "change",
        "original",
        "current",
        "delta",
    }
    assert keys.isdisjoint(forbidden)


def test_texts_do_not_contain_prohibited_claims_or_ids(client):
    text = json.dumps(
        client.get("/api/insights/summary").json(), ensure_ascii=False
    ).lower()
    for forbidden in (
        "питаться лучше",
        "похудели",
        "стали здоровее",
        "экономите деньги",
        "strategy_",
        "menu_plan_",
        "decision_context",
        "event_",
    ):
        assert forbidden not in text


def test_evidence_is_an_allowlisted_reference_only(client):
    body = client.get("/api/insights/summary").json()
    allowed_prefixes = ("trend.", "outcome.", "delta.")
    for insight in body["insights"]:
        sources = insight["evidence"]["sources"]
        assert sources
        assert all(source.startswith(allowed_prefixes) for source in sources)
        assert all(":" not in source and "/" not in source for source in sources)

