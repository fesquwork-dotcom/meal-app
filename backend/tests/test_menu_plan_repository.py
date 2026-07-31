"""Durable MenuPlan persistence: immutability, append-only revisions, CAS."""

import asyncio
import json
from datetime import date

import aiosqlite
import pytest

import config
import database
from menu_plan.exceptions import (
    MenuPlanConcurrencyError,
    MenuPlanNotFoundError,
    MenuPlanPersistenceError,
)
from menu_plan.records import MenuPlanChangeType
from menu_plan.repository import MenuPlanRepository
from strategy.builder import StrategyBuilder
from strategy.exceptions import StrategyPersistenceError
from strategy.repository import StrategyRepository
from tests.menu_fixtures import build_valid_menu_dict
from tests.strategy_fixtures import build_test_profile


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "menu-plan-repo.db"))
    asyncio.run(database.init_db())


def _plan_json(days: int = 3) -> str:
    return json.dumps(build_valid_menu_dict(days=days), ensure_ascii=False)


def _save_with_plan(
    *, user_id: int = 42, menu_plan_id: str, plan_json: str | None = None
) -> str:
    strategy = StrategyBuilder().build(build_test_profile(days=3))
    return asyncio.run(
        StrategyRepository().save_active(
            user_id=user_id,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
            menu_plan_id=menu_plan_id,
            menu_plan_json=plan_json or _plan_json(),
        )
    )


def test_initial_snapshot_saved_with_strategy(db):
    strategy_id = _save_with_plan(menu_plan_id="plan-1")
    repository = MenuPlanRepository()

    record = asyncio.run(repository.get_active_for_user(42))
    assert record is not None
    assert record.id == "plan-1"
    assert record.strategy_id == strategy_id
    assert record.status == "active"
    assert record.current_revision == 1

    revision = asyncio.run(repository.get_revision("plan-1", 1))
    assert revision is not None
    assert revision.change_type == "initial"
    assert revision.plan_json == record.original_plan_json


def test_append_revision_is_cas_guarded(db):
    _save_with_plan(menu_plan_id="plan-1")
    repository = MenuPlanRepository()
    updated_plan = _plan_json(days=3)

    new_revision = asyncio.run(
        repository.append_revision(
            menu_plan_id="plan-1",
            user_id=42,
            expected_revision=1,
            plan_json=updated_plan,
            change_type=MenuPlanChangeType.MEAL_REPLACEMENT,
            changed_meal_ids=["day1_dinner"],
        )
    )
    assert new_revision == 2

    with pytest.raises(MenuPlanConcurrencyError):
        asyncio.run(
            repository.append_revision(
                menu_plan_id="plan-1",
                user_id=42,
                expected_revision=1,
                plan_json=updated_plan,
                change_type=MenuPlanChangeType.MEAL_REPLACEMENT,
            )
        )

    record = asyncio.run(repository.get_by_id("plan-1", 42))
    assert record.current_revision == 2


def test_original_snapshot_is_immutable_after_revisions(db):
    original = _plan_json()
    _save_with_plan(menu_plan_id="plan-1", plan_json=original)
    repository = MenuPlanRepository()
    asyncio.run(
        repository.append_revision(
            menu_plan_id="plan-1",
            user_id=42,
            expected_revision=1,
            plan_json=json.dumps({"summary": "changed"}),
            change_type=MenuPlanChangeType.MEAL_REPLACEMENT,
        )
    )
    record = asyncio.run(repository.get_by_id("plan-1", 42))
    assert record.original_plan_json == original
    first = asyncio.run(repository.get_revision("plan-1", 1))
    assert first.plan_json == original


def test_initial_revision_cannot_be_appended(db):
    _save_with_plan(menu_plan_id="plan-1")
    with pytest.raises(MenuPlanPersistenceError):
        asyncio.run(
            MenuPlanRepository().append_revision(
                menu_plan_id="plan-1",
                user_id=42,
                expected_revision=1,
                plan_json=_plan_json(),
                change_type=MenuPlanChangeType.INITIAL,
            )
        )


def test_ownership_enforced_on_reads_and_writes(db):
    _save_with_plan(menu_plan_id="plan-1")
    repository = MenuPlanRepository()
    with pytest.raises(MenuPlanNotFoundError):
        asyncio.run(repository.get_by_id("plan-1", user_id=99))
    with pytest.raises(MenuPlanNotFoundError):
        asyncio.run(
            repository.append_revision(
                menu_plan_id="plan-1",
                user_id=99,
                expected_revision=1,
                plan_json=_plan_json(),
                change_type=MenuPlanChangeType.MEAL_REPLACEMENT,
            )
        )
    assert asyncio.run(repository.get_active_for_user(99)) is None


def test_new_generation_supersedes_previous_active_plan(db):
    _save_with_plan(menu_plan_id="plan-1")
    _save_with_plan(menu_plan_id="plan-2")
    repository = MenuPlanRepository()

    active = asyncio.run(repository.get_active_for_user(42))
    assert active is not None and active.id == "plan-2"

    previous = asyncio.run(repository.get_by_id("plan-1", 42))
    assert previous.status == "superseded"
    assert previous.superseded_at is not None


def test_strategy_is_not_saved_when_menu_plan_write_fails(db, monkeypatch):
    async def broken_insert(*_args, **_kwargs):
        raise aiosqlite.OperationalError("disk full")

    monkeypatch.setattr(
        "strategy.repository.menu_plan_sql.insert_initial_menu_plan",
        broken_insert,
    )
    with pytest.raises(StrategyPersistenceError):
        _save_with_plan(menu_plan_id="plan-broken")

    async def counts():
        async with aiosqlite.connect(database.resolve_database_path()) as db_conn:
            strategies = await (
                await db_conn.execute("SELECT COUNT(*) FROM weekly_strategies")
            ).fetchone()
            plans = await (
                await db_conn.execute("SELECT COUNT(*) FROM menu_plans")
            ).fetchone()
            return strategies[0], plans[0]

    strategy_count, plan_count = asyncio.run(counts())
    assert strategy_count == 0
    assert plan_count == 0


def test_save_without_menu_plan_keeps_legacy_behavior(db):
    strategy = StrategyBuilder().build(build_test_profile(days=3))
    strategy_id = asyncio.run(
        StrategyRepository().save_active(
            user_id=42,
            strategy=strategy,
            plan_start_date=date(2026, 7, 13),
        )
    )
    assert strategy_id
    assert asyncio.run(MenuPlanRepository().get_active_for_user(42)) is None


def test_parse_plan_handles_malformed_json(db):
    repository = MenuPlanRepository()
    assert repository.parse_plan(None) is None
    assert repository.parse_plan("{not json") is None
    assert repository.parse_plan('"just a string"') is None
    assert repository.parse_plan('{"summary": "ok"}') == {"summary": "ok"}
