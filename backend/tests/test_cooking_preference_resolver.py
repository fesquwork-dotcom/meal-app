"""Tests for cooking preference resolution (Sprint 5.22)."""

from __future__ import annotations

from memory.constants import SignalType
from strategy.context import ProfileContext
from strategy.cooking_preference import (
    PROFILE_FASTER_MEALS_PREFERENCE_APPLIED,
    resolve_cooking_behavior,
    resolve_effective_faster_preference,
)
from strategy.memory_apply import MEMORY_FASTER_APPLIED, MEMORY_IGNORED_PROFILE_PRIORITY
from strategy.memory_context import ConfirmedMemorySignal, StrategyMemoryContext


def _context(**overrides) -> ProfileContext:
    profile = {"allergies": "нет", **overrides}
    return ProfileContext.from_profile(profile)


def _faster_memory() -> StrategyMemoryContext:
    signal = ConfirmedMemorySignal(
        signal_id="f1",
        signal_type=SignalType.PREFER_FASTER_MEALS.value,
        target_value="",
        target_label="Быстрее",
        confirmation_source="user",
    )
    return StrategyMemoryContext(prefer_faster_meals=True, signals=(signal,))


def test_profile_true_enables_preference_without_limit_change():
    context = _context(
        cooktime="slow",
        cooking_preferences={"prefer_faster_meals": True},
    )
    result = resolve_cooking_behavior(
        profile_context=context,
        memory_context=_faster_memory(),
        base_cooking_time_limit=90,
    )
    assert result.cooking_time_limit == 90
    assert result.prefer_faster_meals is True
    assert result.preference_source == "profile"
    assert PROFILE_FASTER_MEALS_PREFERENCE_APPLIED in result.memory_reason_codes


def test_profile_false_ignores_memory():
    context = _context(cooking_preferences={"prefer_faster_meals": False})
    result = resolve_cooking_behavior(
        profile_context=context,
        memory_context=_faster_memory(),
        base_cooking_time_limit=45,
    )
    assert result.prefer_faster_meals is False
    assert MEMORY_IGNORED_PROFILE_PRIORITY in result.memory_reason_codes


def test_unset_memory_downgrades_implicit_limit():
    context = _context()
    result = resolve_cooking_behavior(
        profile_context=context,
        memory_context=_faster_memory(),
        base_cooking_time_limit=45,
    )
    assert result.cooking_time_limit == 20
    assert result.prefer_faster_meals is True
    assert MEMORY_FASTER_APPLIED in result.memory_reason_codes


def test_unset_memory_explicit_cooktime_keeps_limit():
    context = _context(cooktime="slow")
    result = resolve_cooking_behavior(
        profile_context=context,
        memory_context=_faster_memory(),
        base_cooking_time_limit=90,
    )
    assert result.cooking_time_limit == 90
    assert result.prefer_faster_meals is True
    assert MEMORY_FASTER_APPLIED in result.memory_reason_codes


def test_effective_preference_priority():
    profile_true = _context(cooking_preferences={"prefer_faster_meals": True})
    effective_true = resolve_effective_faster_preference(profile_true, _faster_memory())
    assert effective_true.source == "profile"
    assert effective_true.profile_value is True
    assert effective_true.memory_signal_applied is False

    profile_false = _context(cooking_preferences={"prefer_faster_meals": False})
    effective_false = resolve_effective_faster_preference(profile_false, _faster_memory())
    assert effective_false.prefer_faster_meals is False
    assert effective_false.source == "profile"
    assert effective_false.profile_value is False

    unset = _context()
    effective_memory = resolve_effective_faster_preference(unset, _faster_memory())
    assert effective_memory.source == "memory"
    assert effective_memory.memory_signal_applied is True

    effective_default = resolve_effective_faster_preference(unset, StrategyMemoryContext.empty())
    assert effective_default.source == "default"
    assert effective_default.prefer_faster_meals is False
