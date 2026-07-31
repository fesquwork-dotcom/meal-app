"""Tests for deterministic conflict identity."""

from __future__ import annotations

import re

from memory.constants import ConfirmationSource, SignalType
from strategy.conflict_id import CONFLICT_ID_PATTERN, compute_conflict_id
from strategy.conflicts import PREFERRED_PROTEIN_EXCLUDED_BY_MEMORY, detect_strategy_conflicts
from strategy.context import ProfileContext
from strategy.memory_context import ConfirmedMemorySignal, StrategyMemoryContext


def _memory_with_fish_avoid(signal_id: str = "sig-fish") -> StrategyMemoryContext:
    signal = ConfirmedMemorySignal(
        signal_id=signal_id,
        signal_type=SignalType.AVOID_INGREDIENT.value,
        target_value="рыба",
        target_label="Рыба",
        confirmation_source=ConfirmationSource.USER.value,
        updated_at="2026-01-01T00:00:00+00:00",
    )
    return StrategyMemoryContext(avoided_ingredients=("рыба",), signals=(signal,))


def test_conflict_id_stable_for_same_state():
    context = ProfileContext.from_profile(
        {
            "goal": "home",
            "days": 3,
            "budget": 3000,
            "meal_types": ["breakfast", "lunch", "dinner"],
            "proteins": ["fish"],
            "cooktime": "medium",
            "allergies": "нет",
        }
    )
    first, _ = detect_strategy_conflicts(
        context,
        _memory_with_fish_avoid(),
        profile_revision=3,
        preview_version=2,
    )
    second, _ = detect_strategy_conflicts(
        context,
        _memory_with_fish_avoid(),
        profile_revision=3,
        preview_version=2,
    )
    assert first[0].conflict_id == second[0].conflict_id
    assert CONFLICT_ID_PATTERN.match(first[0].conflict_id)


def test_conflict_id_changes_after_profile_revision():
    context = ProfileContext.from_profile(
        {
            "goal": "home",
            "days": 3,
            "budget": 3000,
            "meal_types": ["breakfast", "lunch", "dinner"],
            "proteins": ["fish"],
            "cooktime": "medium",
            "allergies": "нет",
        }
    )
    memory = _memory_with_fish_avoid()
    first, _ = detect_strategy_conflicts(context, memory, profile_revision=1, preview_version=2)
    second, _ = detect_strategy_conflicts(context, memory, profile_revision=2, preview_version=2)
    assert first[0].conflict_id != second[0].conflict_id


def test_conflict_ids_unique_within_preview():
    context = ProfileContext.from_profile(
        {
            "goal": "home",
            "days": 3,
            "budget": 3000,
            "meal_types": ["breakfast", "lunch", "dinner"],
            "proteins": ["fish", "chicken"],
            "cooktime": "medium",
            "allergies": "рыба",
        }
    )
    blocking, _ = detect_strategy_conflicts(context, StrategyMemoryContext.empty(), profile_revision=1)
    ids = [item.conflict_id for item in blocking]
    assert len(ids) == len(set(ids))


def test_conflict_id_does_not_contain_product_label():
    conflict_id = compute_conflict_id(
        code=PREFERRED_PROTEIN_EXCLUDED_BY_MEMORY,
        field="proteins",
        canonical_value="fish",
        memory_signal_id="abc123",
        profile_revision=1,
        preview_version=2,
    )
    assert "рыба" not in conflict_id
    assert "fish" not in conflict_id
    assert re.fullmatch(r"cfl_[a-f0-9]{12}", conflict_id)
