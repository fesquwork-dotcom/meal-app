"""Isolation: effectiveness never feeds Decision / writes preference state."""

from __future__ import annotations

import pathlib


def test_decision_and_strategy_do_not_import_effectiveness():
    backend = pathlib.Path(__file__).resolve().parents[1]
    for package in ("decision", "strategy", "planner", "claude"):
        root = backend / package
        if not root.exists():
            continue
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            assert "learned_preferences.effectiveness" not in source, path
            assert "effectiveness_service" not in source, path
            assert "evaluate_learned_preference_effectiveness" not in source, path


def test_effectiveness_modules_are_read_only():
    package = (
        pathlib.Path(__file__).resolve().parents[1] / "learned_preferences"
    )
    for name in (
        "effectiveness.py",
        "effectiveness_models.py",
        "effectiveness_presentation.py",
        "effectiveness_service.py",
        "observation_repository.py",
    ):
        source = (package / name).read_text(encoding="utf-8")
        for forbidden in (
            "INSERT INTO",
            "UPDATE learned_preferences",
            "transition(",
            "save_active",
            "set_last_review_generation",
            "anthropic",
            "openai",
        ):
            assert forbidden not in source, f"{name}: {forbidden}"


def test_dismiss_review_is_isolated_from_decision_engine():
    service = (
        pathlib.Path(__file__).resolve().parents[1]
        / "learned_preferences"
        / "service.py"
    ).read_text(encoding="utf-8")
    assert "async def dismiss_review" in service
    assert "from decision.engine" not in service
    assert "set_last_review_generation" in service
    # Dismiss must not touch preference status transitions.
    dismiss_block = service.split("async def dismiss_review", 1)[1].split(
        "async def _require_candidate", 1
    )[0]
    assert "transition(" not in dismiss_block
    assert 'target_status="revoked"' not in dismiss_block
    assert 'target_status="active"' not in dismiss_block


def test_effectiveness_does_not_import_decision_engine():
    package = (
        pathlib.Path(__file__).resolve().parents[1] / "learned_preferences"
    )
    for name in (
        "effectiveness.py",
        "effectiveness_service.py",
        "effectiveness_presentation.py",
    ):
        source = (package / name).read_text(encoding="utf-8")
        assert "from decision.engine" not in source, name
        assert "from decision.resolver" not in source, name
