"""API contract for evidence and transparency on GET /api/insights/summary."""

import asyncio
from typing import get_args

import pytest
from fastapi.testclient import TestClient

import config
import database
import main
from insights.evidence_models import InsightLimitation, UnavailableReason
from insights.transparency import (
    COVERAGE_TEXTS,
    PROOF_COLLECTING_TEXT,
    TRANSPARENCY_TITLE,
)


@pytest.fixture(autouse=True)
def _init_test_db(tmp_path, monkeypatch):
    monkeypatch.setattr(
        config, "DATABASE_PATH", str(tmp_path / "insight-transparency.db")
    )
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setattr(config, "ALLOW_DEV_AUTH", True)
    monkeypatch.setattr(config, "DEV_TELEGRAM_USER_ID", 42)
    asyncio.run(database.init_db())


@pytest.fixture
def client():
    return TestClient(main.app)


def test_every_insight_carries_evidence_and_transparency(client):
    body = client.get("/api/insights/summary").json()
    assert len(body["insights"]) == 5
    for insight in body["insights"]:
        evidence = insight["evidence"]
        assert evidence["version"] == 1
        for field in (
            "evidence_weeks",
            "completed_strategies",
            "positive_events",
            "replacement_events",
            "decision_outcomes",
        ):
            assert isinstance(evidence[field], int)
            assert evidence[field] >= 0
        assert evidence["coverage"]["status"] in (
            "insufficient",
            "partial",
            "complete",
        )
        transparency = insight["transparency"]
        assert transparency["title"] == TRANSPARENCY_TITLE
        assert transparency["proof_text"]
        assert transparency["coverage_text"] in COVERAGE_TEXTS.values()


def test_empty_history_reports_insufficient_coverage(client):
    body = client.get("/api/insights/summary").json()
    for insight in body["insights"]:
        coverage = insight["evidence"]["coverage"]
        assert coverage["status"] == "insufficient"
        assert coverage["available_since"] is None
        assert coverage["oldest_plan_date"] is None
        assert coverage["newest_plan_date"] is None
        assert insight["transparency"]["proof_text"] == PROOF_COLLECTING_TEXT
        assert "need_more_completed_plans" in insight["evidence"]["unavailable_reasons"]


def test_limitations_and_reasons_are_allowlisted(client):
    body = client.get("/api/insights/summary").json()
    allowed_limitations = set(get_args(InsightLimitation))
    allowed_reasons = set(get_args(UnavailableReason))
    for insight in body["insights"]:
        assert set(insight["evidence"]["limitations"]) <= allowed_limitations
        assert set(insight["evidence"]["unavailable_reasons"]) <= allowed_reasons


def test_transparency_response_is_deterministic(client, monkeypatch):
    monkeypatch.setattr(
        "insights.service._utc_now_iso",
        lambda: "2026-07-15T12:00:00+00:00",
    )
    first = client.get("/api/insights/summary").json()
    second = client.get("/api/insights/summary").json()
    assert first == second


def test_transparency_payload_contains_no_identifiers(client):
    body = client.get("/api/insights/summary").json()
    for insight in body["insights"]:
        keys = set(insight["evidence"].keys()) | set(insight["transparency"].keys())
        keys |= set(insight["evidence"]["coverage"].keys())
        forbidden = {
            "strategy_id",
            "menu_plan_id",
            "decision_id",
            "event_id",
            "meal_id",
            "profile_revision",
            "user_id",
        }
        assert keys.isdisjoint(forbidden)
