"""Tests for memory-aware StrategyBuilder."""

from __future__ import annotations

import pytest

from memory.constants import ConfirmationSource, SignalType
from strategy import StrategyBuilder, StrategyValidationError
from strategy.memory_context import (
    ConfirmedMemorySignal,
    MAX_MEMORY_AVOIDS_APPLIED,
    StrategyMemoryContext,
)
from strategy.memory_apply import MEMORY_FASTER_APPLIED, MEMORY_PROTEIN_CONFLICT


def _avoid(target: str, *, source: str = "automatic", signal_id: str = "a1") -> StrategyMemoryContext:
    signal = ConfirmedMemorySignal(
        signal_id=signal_id,
        signal_type=SignalType.AVOID_INGREDIENT.value,
        target_value=target,
        target_label=target,
        confirmation_source=source,
    )
    return StrategyMemoryContext(
        avoided_ingredients=(target,),
        signals=(signal,),
    )


def _faster(*, source: str = "automatic") -> StrategyMemoryContext:
    signal = ConfirmedMemorySignal(
        signal_id="f1",
        signal_type=SignalType.PREFER_FASTER_MEALS.value,
        target_value="",
        target_label="Быстрее",
        confirmation_source=source,
    )
    return StrategyMemoryContext(prefer_faster_meals=True, signals=(signal,))


def test_memory_avoid_adds_to_exclusions():
    profile = {"allergies": "орехи", "cooktime": "medium"}
    result = StrategyBuilder().build_with_reasons(profile, _avoid("гречка"))
    excluded = {item.lower() for item in result.strategy.excluded_products}
    assert "орехи" in excluded or any("орех" in item for item in excluded)
    assert any("греч" in item.lower() for item in result.strategy.excluded_products)
    assert "MEMORY_AVOID_INGREDIENT_APPLIED" in result.reason_codes


def test_memory_avoid_does_not_duplicate_profile_exclusion():
    profile = {"allergies": "гречка", "cooktime": "medium"}
    result = StrategyBuilder().build_with_reasons(profile, _avoid("гречка"))
    canonical = [item.lower() for item in result.strategy.excluded_products]
    assert canonical.count("гречка") == 1


def test_empty_memory_preserves_previous_result():
    profile = {"cooktime": "medium", "allergies": "нет"}
    without = StrategyBuilder().build_with_reasons(profile)
    with_empty = StrategyBuilder().build_with_reasons(profile, StrategyMemoryContext.empty())
    assert without.strategy.excluded_products == with_empty.strategy.excluded_products
    assert without.strategy.cooking_time_limit == with_empty.strategy.cooking_time_limit


def test_faster_downgrades_implicit_medium_to_fast():
    profile = {"allergies": "нет"}
    result = StrategyBuilder().build_with_reasons(profile, _faster())
    assert result.strategy.cooking_time_limit == 20
    assert MEMORY_FASTER_APPLIED in result.reason_codes


def test_explicit_slow_keeps_limit_with_faster_preference():
    profile = {"cooktime": "slow"}
    result = StrategyBuilder().build_with_reasons(profile, _faster())
    assert result.strategy.cooking_time_limit == 90
    assert result.strategy.prefer_faster_meals is True
    assert MEMORY_FASTER_APPLIED in result.reason_codes
    profile = {"cooktime": "fast"}
    result = StrategyBuilder().build_with_reasons(profile, _faster())
    assert result.strategy.cooking_time_limit == 20

def test_faster_keeps_fast_at_fast():
    profile = {"cooktime": "medium", "days": 7, "goal": "home"}
    base = StrategyBuilder().build(profile)
    with_faster = StrategyBuilder().build_with_reasons(profile, _faster()).strategy
    assert with_faster.cook_days == base.cook_days


def test_user_confirmed_avoid_conflicts_with_explicit_protein():
    profile = {"proteins": ["fish"], "cooktime": "medium", "allergies": "нет"}
    with pytest.raises(StrategyValidationError) as exc:
        StrategyBuilder().build_with_reasons(
            profile,
            _avoid("рыба", source=ConfirmationSource.USER.value),
        )
    assert exc.value.code == MEMORY_PROTEIN_CONFLICT


def test_automatic_avoid_yields_to_explicit_protein():
    profile = {"proteins": ["fish"], "cooktime": "medium", "allergies": "нет"}
    result = StrategyBuilder().build_with_reasons(
        profile,
        _avoid("рыба", source=ConfirmationSource.AUTOMATIC.value),
    )
    assert result.strategy.preferred_proteins == ["fish"]
    assert not any("рыб" in item.lower() for item in result.strategy.excluded_products)


def test_too_many_memory_avoids_raises_before_strategy():
    signals = tuple(
        ConfirmedMemorySignal(
            signal_id=f"s{i}",
            signal_type=SignalType.AVOID_INGREDIENT.value,
            target_value=f"item{i}",
            target_label=f"item{i}",
            confirmation_source="automatic",
        )
        for i in range(MAX_MEMORY_AVOIDS_APPLIED + 1)
    )
    context = StrategyMemoryContext(
        avoided_ingredients=tuple(f"item{i}" for i in range(MAX_MEMORY_AVOIDS_APPLIED + 1)),
        signals=signals,
    )
    with pytest.raises(StrategyValidationError) as exc:
        StrategyBuilder().build_with_reasons({"allergies": "нет"}, context)
    assert exc.value.code == "MEMORY_TOO_MANY_EXCLUSIONS"


def test_applied_memory_snapshot_persisted_in_build_result():
    result = StrategyBuilder().build_with_reasons({"cooktime": "medium"}, _avoid("гречка"))
    assert result.applied_memory is not None
    assert result.applied_memory.avoided_ingredients == ("гречка",)
