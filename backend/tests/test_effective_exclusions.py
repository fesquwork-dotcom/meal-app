"""Effective exclusion model tests."""

from __future__ import annotations

from strategy.context import ProfileContext
from strategy.effective_exclusions import SAFETY_SOURCES, build_profile_exclusions
from strategy.memory_apply import apply_memory_signals
from strategy.memory_context import StrategyMemoryContext


def test_all_kinds_enter_excluded_products():
    context = ProfileContext.from_profile(
        {
            "allergies": "сельдерей",
            "dietary_constraints": [
                {
                    "id": "dc_aabbccddeeff",
                    "kind": "allergy",
                    "value": "арахис",
                    "canonical_value": "арахис",
                },
                {
                    "id": "dc_bbccddeeff00",
                    "kind": "preference",
                    "value": "рыба",
                    "canonical_value": "рыба",
                },
            ],
        }
    )
    exclusions = build_profile_exclusions(context)
    canonicals = {item.canonical_value for item in exclusions}
    assert "арахис" in canonicals
    assert "сельдерей" in canonicals
    assert "рыба" in canonicals


def test_safety_beats_preference_on_canonical():
    context = ProfileContext.from_profile(
        {
            "allergies": "нет",
            "dietary_constraints": [
                {
                    "id": "dc_1",
                    "kind": "preference",
                    "value": "арахис",
                    "canonical_value": "арахис",
                },
                {
                    "id": "dc_2",
                    "kind": "allergy",
                    "value": "Арахис",
                    "canonical_value": "арахис",
                },
            ],
        }
    )
    exclusions = build_profile_exclusions(context)
    peanut = next(item for item in exclusions if item.canonical_value == "арахис")
    assert peanut.source == "profile_allergy"
    assert not peanut.removable_in_conflict


def test_legacy_is_safety_and_not_removable():
    context = ProfileContext.from_profile({"allergies": "арахис"})
    exclusions = build_profile_exclusions(context)
    assert len(exclusions) == 1
    assert exclusions[0].source == "profile_legacy"
    assert exclusions[0].source in SAFETY_SOURCES
    assert not exclusions[0].removable_in_conflict


def test_memory_redundant_with_profile_constraint():
    from memory.constants import ConfirmationSource, SignalType
    from strategy.memory_context import ConfirmedMemorySignal

    context = ProfileContext.from_profile(
        {
            "allergies": "нет",
            "dietary_constraints": [
                {
                    "id": "dc_1",
                    "kind": "allergy",
                    "value": "арахис",
                    "canonical_value": "арахис",
                }
            ],
        }
    )
    base = [item.display_value for item in build_profile_exclusions(context)]
    signal = ConfirmedMemorySignal(
        signal_id="s1",
        signal_type=SignalType.AVOID_INGREDIENT.value,
        target_value="арахис",
        target_label="Арахис",
        confirmation_source=ConfirmationSource.USER.value,
        updated_at="2026-01-01T00:00:00+00:00",
    )
    memory = StrategyMemoryContext(avoided_ingredients=("арахис",), signals=(signal,))
    result = apply_memory_signals(
        profile_context=context,
        memory_context=memory,
        base_excluded=base,
        base_preferred_proteins=["any"],
        base_cooking_time_limit=45,
    )
    assert result.excluded_products == base
    assert any(
        decision.reason_code == "MEMORY_SIGNAL_REDUNDANT_WITH_PROFILE_CONSTRAINT"
        for decision in result.snapshot.decisions
    )
