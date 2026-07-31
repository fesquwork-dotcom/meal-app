"""Service-layer tests for behavior insights."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

import config
import database
from behavior.constants import BehaviorInsightStatus, BehaviorInsightType
from behavior.engine import BehaviorLearningEngine
from behavior.exceptions import BehaviorEvaluationError, BehaviorServiceUnavailableError
from behavior.keys import compute_insight_key, new_insight_id
from behavior.records import BehaviorInsightRecord
from behavior.repository import BehaviorRepository
from behavior.service import BehaviorService
from memory.records import MemoryEventRecord
from memory.repository import MemoryRepository

NOW = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "behavior-service-test.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(path))
    asyncio.run(database.init_db())
    return path


@pytest.fixture
def service(db_path):
    return BehaviorService()


def _insert_insight(
    *,
    status: str = BehaviorInsightStatus.CANDIDATE.value,
    insight_type: str = BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT.value,
    target_key: str = "recipe-a",
) -> BehaviorInsightRecord:
    key = compute_insight_key(
        user_id=42,
        insight_type=BehaviorInsightType(insight_type),
        target_key=target_key,
    )
    record = BehaviorInsightRecord(
        id=new_insight_id(),
        user_id=42,
        insight_key=key,
        insight_type=insight_type,
        target_key=target_key,
        target_label=None,
        status=status,
        confidence=0.6,
        evidence_count=2,
        evidence_window_days=90,
        rule_version=1,
        first_seen_at=(NOW - timedelta(days=2)).isoformat(),
        last_seen_at=NOW_ISO,
        created_at=NOW_ISO,
        updated_at=NOW_ISO,
        confirmed_at=NOW_ISO if status == BehaviorInsightStatus.CONFIRMED.value else None,
        dismissed_at=None,
        expires_at=(NOW + timedelta(days=180)).isoformat(),
    )

    async def _run():
        await BehaviorRepository()._insert(record)

    asyncio.run(_run())
    return record


def _insert_event(key: str, *, recipe_id: str = "recipe-a") -> None:
    event = MemoryEventRecord(
        id=f"evt-{key}",
        user_id=42,
        event_type="meal_replaced",
        event_key=key,
        strategy_id="s1",
        meal_id="day1_lunch",
        recipe_id=recipe_id,
        reason_code="generic",
        target_type=None,
        target_value=None,
        target_label=None,
        metadata_json=None,
        created_at=NOW_ISO,
    )
    asyncio.run(MemoryRepository().insert_event(event))


def test_list_runs_evaluation_and_returns_candidate(service):
    _insert_event("e1")
    _insert_event("e2")
    body = asyncio.run(service.list_active_insights(42, now=NOW))
    assert body.candidate_count == 1
    assert body.insights[0].status == BehaviorInsightStatus.CANDIDATE
    assert body.insights[0].can_confirm is True


def test_list_hides_observed_dismissed_expired(service):
    _insert_insight(status=BehaviorInsightStatus.OBSERVED.value, target_key="recipe-obs")
    _insert_insight(status=BehaviorInsightStatus.DISMISSED.value, target_key="recipe-dis")
    expired = _insert_insight(status=BehaviorInsightStatus.CANDIDATE.value, target_key="recipe-exp")
    asyncio.run(
        BehaviorRepository().mark_expired(42, expired.id, now=NOW + timedelta(days=200))
    )
    _insert_insight(status=BehaviorInsightStatus.CONFIRMED.value, target_key="recipe-conf")
    body = asyncio.run(service.list_active_insights(42, now=NOW))
    assert len(body.insights) == 1
    assert body.insights[0].status == BehaviorInsightStatus.CONFIRMED


def test_list_stable_ordering(service):
    candidate_low = _insert_insight(
        status=BehaviorInsightStatus.CANDIDATE.value,
        target_key="recipe-c1",
    )
    candidate_high = _insert_insight(
        status=BehaviorInsightStatus.CANDIDATE.value,
        target_key="recipe-c2",
    )
    confirmed = _insert_insight(
        status=BehaviorInsightStatus.CONFIRMED.value,
        target_key="recipe-k",
    )
    asyncio.run(
        BehaviorRepository()._update(
            BehaviorInsightRecord(
                **{
                    **candidate_low.__dict__,
                    "confidence": 0.6,
                    "updated_at": (NOW - timedelta(hours=1)).isoformat(),
                }
            )
        )
    )
    asyncio.run(
        BehaviorRepository()._update(
            BehaviorInsightRecord(
                **{
                    **candidate_high.__dict__,
                    "confidence": 0.9,
                    "updated_at": NOW_ISO,
                }
            )
        )
    )
    body = asyncio.run(service.list_active_insights(42, now=NOW))
    assert [item.id for item in body.insights] == [
        candidate_high.id,
        candidate_low.id,
        confirmed.id,
    ]


def test_presentation_without_recipe_label(service):
    _insert_insight(target_key="recipe-hidden")
    body = asyncio.run(service.list_active_insights(42, now=NOW))
    assert "recipe-hidden" not in body.insights[0].title
    assert "recipe-hidden" not in body.insights[0].description


def test_list_evaluation_failure_falls_back_to_persisted(monkeypatch, service):
    _insert_insight()
    engine = BehaviorLearningEngine()

    async def failing_eval(*_args, **_kwargs):
        raise BehaviorEvaluationError("eval down")

    monkeypatch.setattr(engine, "evaluate_user", failing_eval)
    fallback_service = BehaviorService(engine=engine)
    body = asyncio.run(fallback_service.list_active_insights(42, now=NOW))
    assert body.candidate_count == 1


def test_list_repository_failure_raises_unavailable(monkeypatch, service):
    repo = BehaviorRepository()

    async def failing_list(*_args, **_kwargs):
        raise BehaviorEvaluationError("db down")

    monkeypatch.setattr(repo, "list_active_insights", failing_list)
    unavailable_service = BehaviorService(repository=repo)
    with pytest.raises(BehaviorServiceUnavailableError):
        asyncio.run(unavailable_service.list_active_insights(42, now=NOW))
