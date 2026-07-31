"""Sprint 10.3.3 §8: Replace Meal must stay isolated from generation correction."""

from __future__ import annotations

import inspect

import strategy.prompt as generation_prompt
import strategy.replacement_prompt as replacement_prompt
import strategy.replacement_service as replacement_service


def test_replacement_prompt_does_not_use_generation_targeted_correction():
    """User Replace Meal has its own correction builder — not the week-gen loop."""
    source = inspect.getsource(replacement_prompt)
    assert "build_targeted_correction_prompt" not in source
    assert "build_meal_usage_inventory" not in source
    assert hasattr(replacement_prompt, "build_replacement_correction_prompt")
    # Primary user-facing replace prompt entry points (names may evolve; presence matters).
    assert any(
        hasattr(replacement_prompt, name)
        for name in (
            "build_replacement_user_prompt",
            "build_replace_meal_prompt",
            "build_replacement_system_prompt",
            "build_replacement_prompt",
        )
    )


def test_replacement_service_does_not_call_generate_menu():
    """Single-meal replace must not re-enter weekly generation."""
    source = inspect.getsource(replacement_service)
    assert "generate_menu" not in source
    assert "build_targeted_correction_prompt" not in source


def test_generation_prompt_exports_do_not_shadow_replacement_contract():
    """Shared constants are ok; targeted correction stays generation-only."""
    assert hasattr(generation_prompt, "build_targeted_correction_prompt")
    assert hasattr(replacement_prompt, "build_replacement_correction_prompt")
    assert (
        generation_prompt.build_targeted_correction_prompt
        is not replacement_prompt.build_replacement_correction_prompt
    )
