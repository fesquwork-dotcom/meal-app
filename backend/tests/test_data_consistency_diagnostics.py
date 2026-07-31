"""Sprint 9.5 — data consistency diagnostics unit coverage."""

from __future__ import annotations

import asyncio

import pytest

import config
import database
from dev_tools.consistency import check_user_data_consistency, lifecycle_summary_counts


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATABASE_PATH", str(tmp_path / "cons.db"))
    asyncio.run(database.init_db())


def test_consistency_ok_for_empty_user():
    result = asyncio.run(check_user_data_consistency(42))
    assert result["status"] == "ok"
    assert result["issues"] == []


def test_lifecycle_counts_are_zero_for_fresh_user():
    counts = asyncio.run(lifecycle_summary_counts(42))
    assert counts["strategies"] == 0
    assert counts["learned_preferences"] == 0
