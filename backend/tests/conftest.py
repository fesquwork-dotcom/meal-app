"""Shared pytest configuration for backend tests."""

from __future__ import annotations

import pytest

import config


@pytest.fixture(autouse=True)
def _disable_budget_optimizer_in_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Finite mock Claude response lists must not be consumed by a soft upgrade pass."""
    monkeypatch.setattr(config, "BUDGET_OPTIMIZER_ENABLED", False)
