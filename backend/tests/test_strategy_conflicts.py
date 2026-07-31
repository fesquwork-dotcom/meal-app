"""Tests for deterministic strategy conflict detection."""

from __future__ import annotations

from memory.constants import ConfirmationSource, SignalType
from strategy.conflicts import (
    EXPLICIT_COOKTIME_OVERRIDES_MEMORY,
    LEGACY_CONSTRAINTS_REQUIRE_REVIEW,
    MEMORY_AVOID_IGNORED_FOR_PROTEIN,
    NO_ALLOWED_PREFERRED_PROTEINS,
    PREFERRED_PROTEIN_BLOCKED_BY_ALLERGY,
    PREFERRED_PROTEIN_BLOCKED_BY_LEGACY_CONSTRAINT,
    PREFERRED_PROTEIN_EXCLUDED_BY_MEMORY,
    PREFERRED_PROTEIN_EXCLUDED_BY_PROFILE_PREFERENCE,
    TOO_MANY_MEMORY_EXCLUSIONS,
    detect_strategy_conflicts,
)
from strategy.context import ProfileContext
from strategy.memory_context import ConfirmedMemorySignal, StrategyMemoryContext


def _context(**overrides: object) -> ProfileContext:
    profile = {
        "goal": "home",
        "days": 7,
        "budget": 3000,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "proteins": ["any"],
        "cooktime": "medium",
        "allergies": "нет",
    }
    profile.update(overrides)
    return ProfileContext.from_profile(profile)


def _avoid(
    target: str,
    *,
    source: str = ConfirmationSource.USER.value,
    signal_id: str = "s1",
) -> StrategyMemoryContext:
    signal = ConfirmedMemorySignal(
        signal_id=signal_id,
        signal_type=SignalType.AVOID_INGREDIENT.value,
        target_value=target,
        target_label=target,
        confirmation_source=source,
        updated_at="2026-01-01T00:00:00+00:00",
    )
    return StrategyMemoryContext(avoided_ingredients=(target,), signals=(signal,))


def test_profile_protein_excluded_by_legacy_constraint():
    context = _context(proteins=["fish"], allergies="рыба")
    blocking, warnings = detect_strategy_conflicts(context, StrategyMemoryContext.empty())
    assert any(
        item.conflict.code == PREFERRED_PROTEIN_BLOCKED_BY_LEGACY_CONSTRAINT for item in blocking
    )
    assert not any(
        opt.action == "remove_profile_preference"
        for item in blocking
        for opt in item.conflict.options
    )


def test_profile_protein_excluded_by_allergy_constraint():
    context = _context(
        proteins=["fish"],
        dietary_constraints=[
            {"id": "dc_aabbccddeeff", "kind": "allergy", "value": "рыба", "canonical_value": "рыба"}
        ],
        allergies="нет",
    )
    blocking, _ = detect_strategy_conflicts(context, StrategyMemoryContext.empty())
    assert any(item.conflict.code == PREFERRED_PROTEIN_BLOCKED_BY_ALLERGY for item in blocking)


def test_profile_protein_excluded_by_preference_has_removable_option():
    context = _context(
        proteins=["fish"],
        dietary_constraints=[
            {
                "id": "dc_aabbccddeeff",
                "kind": "preference",
                "value": "рыба",
                "canonical_value": "рыба",
            }
        ],
        allergies="нет",
    )
    blocking, _ = detect_strategy_conflicts(context, StrategyMemoryContext.empty())
    assert any(
        item.conflict.code == PREFERRED_PROTEIN_EXCLUDED_BY_PROFILE_PREFERENCE for item in blocking
    )
    assert any(
        opt.action == "remove_profile_preference"
        for item in blocking
        for opt in item.conflict.options
    )


def test_legacy_constraints_emit_review_warning():
    context = _context(allergies="арахис, сельдерей")
    _, warnings = detect_strategy_conflicts(context, StrategyMemoryContext.empty())
    assert any(item.conflict.code == LEGACY_CONSTRAINTS_REQUIRE_REVIEW for item in warnings)


def test_user_confirmed_memory_avoid_conflicts_with_explicit_protein():
    context = _context(proteins=["fish"])
    blocking, _ = detect_strategy_conflicts(context, _avoid("рыба"))
    assert any(item.conflict.code == PREFERRED_PROTEIN_EXCLUDED_BY_MEMORY for item in blocking)


def test_automatic_memory_avoid_yields_warning_not_blocking():
    context = _context(proteins=["fish"])
    blocking, warnings = detect_strategy_conflicts(
        context,
        _avoid("рыба", source=ConfirmationSource.AUTOMATIC.value),
    )
    assert not blocking
    assert any(item.conflict.code == MEMORY_AVOID_IGNORED_FOR_PROTEIN for item in warnings)


def test_multiple_proteins_with_one_excluded_is_ready():
    context = _context(proteins=["fish", "chicken"])
    blocking, warnings = detect_strategy_conflicts(context, _avoid("рыба"))
    assert not blocking
    assert any(item.conflict.severity == "warning" for item in warnings)


def test_explicit_cooktime_allows_faster_preference_without_warning():
    context = _context(cooktime="slow", proteins=["any"])
    faster = ConfirmedMemorySignal(
        signal_id="f1",
        signal_type=SignalType.PREFER_FASTER_MEALS.value,
        target_value="",
        target_label="Быстрее",
        confirmation_source=ConfirmationSource.USER.value,
        updated_at="2026-01-01T00:00:00+00:00",
    )
    memory = StrategyMemoryContext(prefer_faster_meals=True, signals=(faster,))
    blocking, warnings = detect_strategy_conflicts(context, memory)
    assert not blocking
    assert not any(
        item.conflict.code == EXPLICIT_COOKTIME_OVERRIDES_MEMORY for item in warnings
    )


def test_too_many_memory_exclusions_blocking():
    signals = tuple(
        ConfirmedMemorySignal(
            signal_id=f"s{i}",
            signal_type=SignalType.AVOID_INGREDIENT.value,
            target_value=f"item{i}",
            target_label=f"item{i}",
            confirmation_source=ConfirmationSource.AUTOMATIC.value,
            updated_at="2026-01-01T00:00:00+00:00",
        )
        for i in range(31)
    )
    memory = StrategyMemoryContext(
        avoided_ingredients=tuple(f"item{i}" for i in range(31)),
        signals=signals,
    )
    blocking, _ = detect_strategy_conflicts(_context(), memory)
    assert any(item.conflict.code == TOO_MANY_MEMORY_EXCLUSIONS for item in blocking)


def test_no_conflicts_for_empty_memory_and_profile():
    blocking, warnings = detect_strategy_conflicts(_context(), StrategyMemoryContext.empty())
    assert blocking == []
    assert warnings == []


def test_detection_is_deterministic_and_does_not_mutate_inputs():
    context = _context(proteins=["fish"])
    memory = _avoid("рыба")
    first_blocking, _ = detect_strategy_conflicts(context, memory)
    second_blocking, _ = detect_strategy_conflicts(context, memory)
    assert first_blocking[0].conflict.conflict_id == second_blocking[0].conflict.conflict_id
    assert context.proteins == ["fish"]
