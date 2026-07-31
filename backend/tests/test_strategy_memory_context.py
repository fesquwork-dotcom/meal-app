"""Tests for StrategyMemoryContext builder."""

from __future__ import annotations

import pytest

from memory.constants import ConfirmationSource, SignalStatus, SignalType
from memory.records import PreferenceSignalRecord
from strategy.memory_context import (
    AppliedMemorySnapshot,
    MAX_MEMORY_AVOIDS_APPLIED,
    StrategyMemoryContext,
    build_strategy_memory_context,
)


def _signal(**overrides: object) -> PreferenceSignalRecord:
    defaults: dict[str, object] = {
        "id": "sig-1",
        "user_id": 42,
        "signal_type": SignalType.AVOID_INGREDIENT.value,
        "target_value": "гречка",
        "target_label": "Гречка",
        "status": SignalStatus.CONFIRMED.value,
        "confidence": 1.0,
        "evidence_count": 3,
        "first_observed_at": "2026-01-01T00:00:00+00:00",
        "last_observed_at": "2026-01-01T00:00:00+00:00",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
        "dismissed_at": None,
        "confirmation_source": ConfirmationSource.AUTOMATIC.value,
    }
    defaults.update(overrides)
    return PreferenceSignalRecord(**defaults)  # type: ignore[arg-type]


def test_confirmed_avoid_enters_context():
    context = build_strategy_memory_context([_signal()])
    assert context.avoided_ingredients == ("гречка",)
    assert context.signals[0].confirmation_source == ConfirmationSource.AUTOMATIC.value


def test_observed_avoid_ignored():
    context = build_strategy_memory_context(
        [_signal(status=SignalStatus.OBSERVED.value, confirmation_source=None)]
    )
    assert context.avoided_ingredients == ()
    assert context.signals == ()


def test_dismissed_avoid_ignored():
    context = build_strategy_memory_context(
        [_signal(status=SignalStatus.DISMISSED.value)]
    )
    assert context.avoided_ingredients == ()


def test_confirmed_faster_enters_context():
    context = build_strategy_memory_context(
        [
            _signal(
                id="f1",
                signal_type=SignalType.PREFER_FASTER_MEALS.value,
                target_value="",
                target_label="Быстрее",
            )
        ]
    )
    assert context.prefer_faster_meals is True


def test_unknown_signal_type_ignored_in_avoids():
    context = build_strategy_memory_context(
        [_signal(signal_type="unknown_type", target_value="x")]
    )
    assert context.avoided_ingredients == ()
    assert len(context.signals) == 1


def test_targets_deduplicated_and_sorted():
    context = build_strategy_memory_context(
        [
            _signal(id="a", target_value="сельдерей"),
            _signal(id="b", target_value="гречка"),
            _signal(id="c", target_value="гречка"),
        ]
    )
    assert context.avoided_ingredients == ("гречка", "сельдерей")


def test_context_is_immutable():
    context = build_strategy_memory_context([_signal()])
    with pytest.raises(AttributeError):
        context.avoided_ingredients = ()  # type: ignore[misc]


def test_legacy_confirmed_defaults_to_automatic_provenance():
    context = build_strategy_memory_context(
        [_signal(confirmation_source=None)]
    )
    assert context.signals[0].confirmation_source == ConfirmationSource.AUTOMATIC.value


def test_applied_memory_snapshot_round_trip():
    snapshot = AppliedMemorySnapshot(
        avoided_ingredients=("гречка",),
        prefer_faster_meals=True,
        decisions=(),
    )
    restored = AppliedMemorySnapshot.from_json(snapshot.to_json())
    assert restored is not None
    assert restored.avoided_ingredients == ("гречка",)
    assert restored.prefer_faster_meals is True


def test_malformed_applied_memory_returns_none():
    assert AppliedMemorySnapshot.from_json("{not json") is None
    assert AppliedMemorySnapshot.from_json(None) is None


def test_empty_context_factory():
    assert StrategyMemoryContext.empty().avoided_ingredients == ()


def test_max_avoid_signals_collected_for_apply_layer():
    signals = [
        _signal(id=f"s{i}", target_value=f"item{i}")
        for i in range(MAX_MEMORY_AVOIDS_APPLIED + 5)
    ]
    context = build_strategy_memory_context(signals)
    assert len(context.avoided_ingredients) == MAX_MEMORY_AVOIDS_APPLIED + 5
