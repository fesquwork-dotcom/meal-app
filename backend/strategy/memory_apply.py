"""Deterministic application of confirmed memory signals to strategy fields."""

from __future__ import annotations

from dataclasses import dataclass

from memory.constants import ConfirmationSource, SignalType
from shopping.normalization import canonical_ingredient_name, display_ingredient_name
from strategy.context import ProfileContext
from strategy.exceptions import StrategyValidationError
from strategy.memory_context import (
    AppliedMemoryDecision,
    AppliedMemorySnapshot,
    ConfirmedMemorySignal,
    MAX_MEMORY_AVOIDS_APPLIED,
    StrategyMemoryContext,
)
MEMORY_AVOID_APPLIED = "MEMORY_AVOID_INGREDIENT_APPLIED"
MEMORY_FASTER_APPLIED = "MEMORY_FASTER_MEALS_APPLIED"
MEMORY_IGNORED_PROFILE_PRIORITY = "MEMORY_SIGNAL_IGNORED_PROFILE_PRIORITY"
MEMORY_IGNORED_INVALID_TARGET = "MEMORY_SIGNAL_IGNORED_INVALID_TARGET"
MEMORY_PROTEIN_CONFLICT = "MEMORY_PROTEIN_CONFLICT"
MEMORY_TOO_MANY_EXCLUSIONS = "MEMORY_TOO_MANY_EXCLUSIONS"
MEMORY_REDUNDANT_WITH_PROFILE = "MEMORY_SIGNAL_REDUNDANT_WITH_PROFILE_CONSTRAINT"

FASTER_DOWNGRADE: dict[int, int] = {90: 45, 45: 20, 20: 20}

# Map preferred protein codes to canonical ingredient keys for conflict checks.
PROTEIN_CANONICAL_KEYS: dict[str, str] = {
    "chicken": "курица",
    "beef": "говядина",
    "pork": "свинина",
    "fish": "рыба",
    "seafood": "морепродукты",
    "eggs": "яйца",
    "veggie": "овощи",
}

from strategy.cooking_preference import resolve_cooking_behavior


@dataclass(frozen=True)
class MemoryApplyResult:
    excluded_products: list[str]
    preferred_proteins: list[str]
    cooking_time_limit: int
    prefer_faster_meals: bool
    memory_reason_codes: list[str]
    snapshot: AppliedMemorySnapshot


def _canonical_set(values: list[str]) -> set[str]:
    return {canonical_ingredient_name(value) for value in values if value.strip()}


def _merge_exclusions(profile_excluded: list[str], memory_avoids: tuple[str, ...]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()

    for item in profile_excluded:
        canonical = canonical_ingredient_name(item)
        if canonical not in seen:
            seen.add(canonical)
            merged.append(item.strip())

    for canonical in memory_avoids:
        if not canonical or canonical in seen:
            continue
        seen.add(canonical)
        merged.append(display_ingredient_name(canonical))

    return merged


def _protein_conflicts_with_avoid(protein: str, avoid_canonical: str) -> bool:
    if protein == "any":
        return False
    mapped = PROTEIN_CANONICAL_KEYS.get(protein)
    if mapped and canonical_ingredient_name(mapped) == avoid_canonical:
        return True
    return canonical_ingredient_name(protein) == avoid_canonical


def apply_memory_signals(
    *,
    profile_context: ProfileContext,
    memory_context: StrategyMemoryContext,
    base_excluded: list[str],
    base_preferred_proteins: list[str],
    base_cooking_time_limit: int,
    learned_prefer_faster: bool | None = None,
) -> MemoryApplyResult:
    """Applies confirmed memory to strategy fields without mutating inputs."""
    if not memory_context.signals:
        # Sprint 9.2.1: cooking preference resolution must not depend on
        # unrelated Memory signals. The single source-priority resolver
        # (Profile > Learned > Memory > default) runs unconditionally, so an
        # explicit Profile faster preference survives an empty Memory context.
        cooking_behavior = resolve_cooking_behavior(
            profile_context=profile_context,
            memory_context=memory_context,
            base_cooking_time_limit=base_cooking_time_limit,
            learned_prefer_faster=learned_prefer_faster,
        )
        return MemoryApplyResult(
            excluded_products=list(base_excluded),
            preferred_proteins=list(base_preferred_proteins),
            cooking_time_limit=cooking_behavior.cooking_time_limit,
            prefer_faster_meals=cooking_behavior.prefer_faster_meals,
            memory_reason_codes=sorted(set(cooking_behavior.memory_reason_codes)),
            snapshot=AppliedMemorySnapshot(
                prefer_faster_meals=cooking_behavior.prefer_faster_meals,
            ),
        )

    decisions: list[AppliedMemoryDecision] = []
    memory_reason_codes: list[str] = []
    effective_proteins = list(base_preferred_proteins)
    explicit_proteins = profile_context.proteins_explicit and profile_context.proteins != ["any"]

    applied_avoids: list[str] = []
    avoid_signals = [
        signal
        for signal in memory_context.signals
        if signal.signal_type == SignalType.AVOID_INGREDIENT.value
    ]

    if len(avoid_signals) > len(memory_context.avoided_ingredients):
        # Defensive: only deduplicated targets are eligible.
        pass

    total_exclusions_estimate = len(_canonical_set(base_excluded)) + len(memory_context.avoided_ingredients)
    if len(avoid_signals) > MAX_MEMORY_AVOIDS_APPLIED:
        raise StrategyValidationError(
            "Too many confirmed memory exclusions to apply safely",
            code=MEMORY_TOO_MANY_EXCLUSIONS,
        )

    base_excluded_canonical = _canonical_set(base_excluded)

    for signal in avoid_signals:
        target = signal.target_value.strip()
        if not target:
            decisions.append(
                AppliedMemoryDecision(
                    signal_id=signal.signal_id,
                    signal_type=signal.signal_type,
                    target_value=None,
                    confirmation_source=signal.confirmation_source,
                    applied=False,
                    reason_code=MEMORY_IGNORED_INVALID_TARGET,
                )
            )
            memory_reason_codes.append(MEMORY_IGNORED_INVALID_TARGET)
            continue

        if canonical_ingredient_name(target) in base_excluded_canonical:
            # The product is already excluded by a profile constraint; do not
            # create a duplicate decision or double-explain the exclusion.
            decisions.append(
                AppliedMemoryDecision(
                    signal_id=signal.signal_id,
                    signal_type=signal.signal_type,
                    target_value=target,
                    confirmation_source=signal.confirmation_source,
                    applied=False,
                    reason_code=MEMORY_REDUNDANT_WITH_PROFILE,
                )
            )
            memory_reason_codes.append(MEMORY_REDUNDANT_WITH_PROFILE)
            continue

        conflicting_proteins = [
            protein
            for protein in effective_proteins
            if _protein_conflicts_with_avoid(protein, target)
        ]

        if conflicting_proteins:
            remaining_proteins = [
                protein for protein in effective_proteins if protein not in conflicting_proteins
            ]
            if (
                signal.confirmation_source == ConfirmationSource.USER.value
                and explicit_proteins
                and not remaining_proteins
            ):
                raise StrategyValidationError(
                    "Confirmed memory avoid conflicts with explicit preferred protein",
                    code=MEMORY_PROTEIN_CONFLICT,
                )
            if remaining_proteins and explicit_proteins:
                effective_proteins = remaining_proteins
            elif (
                signal.confirmation_source == ConfirmationSource.USER.value
                and explicit_proteins
            ):
                raise StrategyValidationError(
                    "Confirmed memory avoid conflicts with explicit preferred protein",
                    code=MEMORY_PROTEIN_CONFLICT,
                )
            elif explicit_proteins:
                decisions.append(
                    AppliedMemoryDecision(
                        signal_id=signal.signal_id,
                        signal_type=signal.signal_type,
                        target_value=target,
                        confirmation_source=signal.confirmation_source,
                        applied=False,
                        reason_code=MEMORY_IGNORED_PROFILE_PRIORITY,
                    )
                )
                memory_reason_codes.append(MEMORY_IGNORED_PROFILE_PRIORITY)
                continue

        if target not in applied_avoids:
            applied_avoids.append(target)
        decisions.append(
            AppliedMemoryDecision(
                signal_id=signal.signal_id,
                signal_type=signal.signal_type,
                target_value=target,
                confirmation_source=signal.confirmation_source,
                applied=True,
                reason_code=MEMORY_AVOID_APPLIED,
            )
        )

    excluded_products = _merge_exclusions(base_excluded, tuple(applied_avoids))
    if applied_avoids:
        memory_reason_codes.append(MEMORY_AVOID_APPLIED)

    cooking_behavior = resolve_cooking_behavior(
        profile_context=profile_context,
        memory_context=memory_context,
        base_cooking_time_limit=base_cooking_time_limit,
        learned_prefer_faster=learned_prefer_faster,
    )
    if cooking_behavior.faster_decision is not None:
        decisions.append(cooking_behavior.faster_decision)
    memory_reason_codes.extend(cooking_behavior.memory_reason_codes)

    if not effective_proteins:
        effective_proteins = ["any"]

    snapshot = AppliedMemorySnapshot(
        avoided_ingredients=tuple(applied_avoids),
        prefer_faster_meals=cooking_behavior.prefer_faster_meals,
        decisions=tuple(decisions),
    )

    return MemoryApplyResult(
        excluded_products=excluded_products,
        preferred_proteins=effective_proteins,
        cooking_time_limit=cooking_behavior.cooking_time_limit,
        prefer_faster_meals=cooking_behavior.prefer_faster_meals,
        memory_reason_codes=sorted(set(memory_reason_codes)),
        snapshot=snapshot,
    )
