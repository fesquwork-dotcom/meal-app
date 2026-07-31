"""Persistence tests for behavior insights."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import aiosqlite
import pytest

import config
import database
from behavior.constants import (
    BEHAVIOR_RULES_VERSION,
    BehaviorInsightStatus,
    BehaviorInsightType,
)
from behavior.exceptions import (
    BehaviorEvaluationError,
    BehaviorInsightInvalidTransitionError,
    BehaviorInsightNotConfirmableError,
    BehaviorInsightNotDismissibleError,
    BehaviorInsightNotFoundError,
)
from behavior.keys import compute_insight_key, new_insight_id
from behavior.models import BehaviorInsightCandidate
from behavior.records import BehaviorInsightRecord
from behavior.repository import BehaviorRepository

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "behavior-test.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    asyncio.run(database.init_db())
    return path


@pytest.fixture
def repository(db_path):
    return BehaviorRepository()


def _candidate(
    *,
    insight_type: BehaviorInsightType = BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT,
    target_key: str = "recipe-a",
    status: BehaviorInsightStatus = BehaviorInsightStatus.CANDIDATE,
    evidence_count: int = 2,
) -> BehaviorInsightCandidate:
    return BehaviorInsightCandidate(
        insight_type=insight_type,
        target_key=target_key,
        target_label=None,
        status=status,
        confidence=0.6,
        evidence_count=evidence_count,
        evidence_window_days=90,
        first_seen_at=(NOW - timedelta(days=3)).isoformat(),
        last_seen_at=NOW_ISO,
    )


def _insert_raw(record: BehaviorInsightRecord) -> None:
    async def _run():
        repo = BehaviorRepository()
        await repo._insert(record)

    asyncio.run(_run())


def _base_record(
    *,
    user_id: int = 42,
    status: str = BehaviorInsightStatus.CANDIDATE.value,
    insight_id: str | None = None,
    target_key: str = "recipe-a",
) -> BehaviorInsightRecord:
    candidate = _candidate(status=BehaviorInsightStatus(status), target_key=target_key)
    key = compute_insight_key(
        user_id=user_id,
        insight_type=candidate.insight_type,
        target_key=candidate.target_key,
    )
    return BehaviorInsightRecord(
        id=insight_id or new_insight_id(),
        user_id=user_id,
        insight_key=key,
        insight_type=candidate.insight_type.value,
        target_key=candidate.target_key,
        target_label=None,
        status=status,
        confidence=0.6,
        evidence_count=2,
        evidence_window_days=90,
        rule_version=BEHAVIOR_RULES_VERSION,
        first_seen_at=candidate.first_seen_at,
        last_seen_at=candidate.last_seen_at,
        created_at=NOW_ISO,
        updated_at=NOW_ISO,
        confirmed_at=None,
        dismissed_at=None,
        expires_at=(NOW + timedelta(days=180)).isoformat(),
    )


def test_behavior_tables_and_indexes_exist(db_path):
    async def _check():
        async with aiosqlite.connect(db_path) as db:
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='behavior_insights'"
            )
            table = await cursor.fetchone()
            await cursor.close()
            cursor = await db.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='behavior_insights'"
            )
            indexes = {row[0] for row in await cursor.fetchall()}
            await cursor.close()
        return table, indexes

    table, indexes = asyncio.run(_check())
    assert table is not None
    assert "idx_behavior_insights_user_key" in indexes
    assert "idx_behavior_insights_user_id" in indexes
    assert "idx_behavior_insights_user_status" in indexes
    assert "idx_behavior_insights_user_type" in indexes
    assert "idx_behavior_insights_expires_at" in indexes


def test_insert_and_get_by_id(repository):
    record = _base_record()
    _insert_raw(record)
    loaded = asyncio.run(repository.get_by_id(record.user_id, record.id))
    assert loaded == record


def test_get_by_id_ownership(repository):
    record = _base_record(user_id=42)
    _insert_raw(record)
    assert asyncio.run(repository.get_by_id(99, record.id)) is None


def test_get_by_key(repository):
    record = _base_record()
    _insert_raw(record)
    loaded = asyncio.run(repository.get_by_key(record.user_id, record.insight_key))
    assert loaded is not None
    assert loaded.id == record.id


def test_upsert_creates_and_updates(repository):
    candidate = _candidate()
    record, was_created, was_updated = asyncio.run(
        repository.upsert_insight(42, candidate, existing=None, now=NOW)
    )
    assert was_created is True
    assert was_updated is False
    created = record

    key = compute_insight_key(
        user_id=42,
        insight_type=candidate.insight_type,
        target_key=candidate.target_key,
    )
    existing = asyncio.run(repository.get_by_key(42, key))
    updated_candidate = BehaviorInsightCandidate(
        insight_type=candidate.insight_type,
        target_key=candidate.target_key,
        target_label=None,
        status=BehaviorInsightStatus.CANDIDATE,
        confidence=0.8,
        evidence_count=3,
        evidence_window_days=90,
        first_seen_at=candidate.first_seen_at,
        last_seen_at=NOW_ISO,
    )
    record, was_created, was_updated = asyncio.run(
        repository.upsert_insight(42, updated_candidate, existing=existing, now=NOW)
    )
    assert was_created is False
    assert was_updated is True
    assert record.evidence_count == 3
    assert record.first_seen_at == candidate.first_seen_at


def test_unique_insight_key_enforced(db_path):
    first = _base_record(insight_id="bi_first")
    second = _base_record(insight_id="bi_second")
    _insert_raw(first)
    with pytest.raises(BehaviorEvaluationError):
        _insert_raw(second)


def test_list_by_status(repository):
    observed = _base_record(
        status=BehaviorInsightStatus.OBSERVED.value,
        insight_id="bi_obs",
        target_key="recipe-obs",
    )
    candidate = _base_record(
        status=BehaviorInsightStatus.CANDIDATE.value,
        insight_id="bi_cand",
        target_key="recipe-cand",
    )
    _insert_raw(observed)
    _insert_raw(candidate)
    rows = asyncio.run(
        repository.list_by_status(
            42,
            [BehaviorInsightStatus.CANDIDATE.value],
        )
    )
    assert len(rows) == 1
    assert rows[0].id == "bi_cand"


def test_confirm_transition(repository):
    record = _base_record()
    _insert_raw(record)
    confirmed = asyncio.run(repository.confirm(42, record.id, now=NOW))
    assert confirmed.status == BehaviorInsightStatus.CONFIRMED.value
    assert confirmed.confidence == 1.0
    assert confirmed.confirmed_at == NOW_ISO


def test_confirm_idempotent(repository):
    record = _base_record(status=BehaviorInsightStatus.CONFIRMED.value)
    record = BehaviorInsightRecord(
        **{**record.__dict__, "confirmed_at": NOW_ISO, "confidence": 1.0}
    )
    _insert_raw(record)
    again = asyncio.run(repository.confirm(42, record.id, now=NOW))
    assert again.status == BehaviorInsightStatus.CONFIRMED.value


def test_confirm_invalid_from_observed(repository):
    record = _base_record(status=BehaviorInsightStatus.OBSERVED.value)
    _insert_raw(record)
    with pytest.raises(BehaviorInsightNotConfirmableError):
        asyncio.run(repository.confirm(42, record.id, now=NOW))


def test_dismiss_transition(repository):
    record = _base_record()
    _insert_raw(record)
    dismissed = asyncio.run(repository.dismiss(42, record.id, now=NOW))
    assert dismissed.status == BehaviorInsightStatus.DISMISSED.value
    assert dismissed.dismissed_at == NOW_ISO


def test_dismiss_invalid_from_confirmed(repository):
    record = _base_record(status=BehaviorInsightStatus.CONFIRMED.value)
    record = BehaviorInsightRecord(
        **{**record.__dict__, "confirmed_at": NOW_ISO, "confidence": 1.0}
    )
    _insert_raw(record)
    with pytest.raises(BehaviorInsightNotDismissibleError):
        asyncio.run(repository.dismiss(42, record.id, now=NOW))


def test_dismissed_not_reopened_on_upsert(repository):
    record = _base_record(status=BehaviorInsightStatus.DISMISSED.value)
    record = BehaviorInsightRecord(**{**record.__dict__, "dismissed_at": NOW_ISO})
    _insert_raw(record)
    candidate = _candidate(evidence_count=5)
    updated, created, changed = asyncio.run(
        repository.upsert_insight(42, candidate, existing=record, now=NOW)
    )
    assert created is False
    assert changed is False
    assert updated.status == BehaviorInsightStatus.DISMISSED.value


def test_mark_expired(repository):
    record = _base_record()
    _insert_raw(record)
    expired = asyncio.run(repository.mark_expired(42, record.id, now=NOW))
    assert expired.status == BehaviorInsightStatus.EXPIRED.value


def test_mark_expired_skips_confirmed(repository):
    record = _base_record(status=BehaviorInsightStatus.CONFIRMED.value)
    record = BehaviorInsightRecord(
        **{**record.__dict__, "confirmed_at": NOW_ISO, "confidence": 1.0}
    )
    _insert_raw(record)
    with pytest.raises(BehaviorInsightInvalidTransitionError):
        asyncio.run(repository.mark_expired(42, record.id, now=NOW))


def test_expire_due_insights(repository):
    due = _base_record(insight_id="bi_due", target_key="recipe-due")
    due_key = compute_insight_key(
        user_id=42,
        insight_type=BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT,
        target_key="recipe-due",
    )
    due = BehaviorInsightRecord(
        **{
            **due.__dict__,
            "insight_key": due_key,
            "target_key": "recipe-due",
            "expires_at": (NOW - timedelta(days=1)).isoformat(),
        }
    )
    confirmed = _base_record(
        status=BehaviorInsightStatus.CONFIRMED.value,
        insight_id="bi_conf",
        target_key="recipe-conf",
    )
    conf_key = compute_insight_key(
        user_id=42,
        insight_type=BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT,
        target_key="recipe-conf",
    )
    confirmed = BehaviorInsightRecord(
        **{
            **confirmed.__dict__,
            "insight_key": conf_key,
            "target_key": "recipe-conf",
            "confirmed_at": NOW_ISO,
            "confidence": 1.0,
            "expires_at": (NOW - timedelta(days=1)).isoformat(),
        }
    )
    _insert_raw(due)
    _insert_raw(confirmed)
    count = asyncio.run(repository.expire_due_insights(42, NOW))
    assert count == 1
    still_confirmed = asyncio.run(repository.get_by_id(42, "bi_conf"))
    assert still_confirmed.status == BehaviorInsightStatus.CONFIRMED.value


def test_not_found_errors(repository):
    with pytest.raises(BehaviorInsightNotFoundError):
        asyncio.run(repository.confirm(42, "missing", now=NOW))
