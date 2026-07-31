"""Immutable confirmed behavior context for strategy building (Sprint 5.26)."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from behavior.constants import BehaviorInsightStatus, BehaviorInsightType
from behavior.records import BehaviorInsightRecord

logger = logging.getLogger(__name__)

BEHAVIOR_CONTEXT_VERSION = 1


@dataclass(frozen=True)
class ConfirmedBehaviorInsight:
    insight_id: str
    insight_type: BehaviorInsightType
    target_key: str | None
    confidence: float
    evidence_count: int
    rule_version: int
    updated_at: str


@dataclass(frozen=True)
class StrategyBehaviorContext:
    frequent_recipe_replacements: tuple[ConfirmedBehaviorInsight, ...]
    ingredient_availability_frictions: tuple[ConfirmedBehaviorInsight, ...]
    high_replacement_rate: bool
    insights: tuple[ConfirmedBehaviorInsight, ...]

    @classmethod
    def empty(cls) -> "StrategyBehaviorContext":
        return cls(
            frequent_recipe_replacements=(),
            ingredient_availability_frictions=(),
            high_replacement_rate=False,
            insights=(),
        )


def _record_to_confirmed(record: BehaviorInsightRecord) -> ConfirmedBehaviorInsight | None:
    if record.status != BehaviorInsightStatus.CONFIRMED.value:
        return None
    try:
        insight_type = BehaviorInsightType(record.insight_type)
    except ValueError:
        logger.warning(
            "behavior_context_malformed_type insight_type=%s",
            record.insight_type,
        )
        return None
    return ConfirmedBehaviorInsight(
        insight_id=record.id,
        insight_type=insight_type,
        target_key=record.target_key,
        confidence=record.confidence,
        evidence_count=record.evidence_count,
        rule_version=record.rule_version,
        updated_at=record.updated_at,
    )


def build_strategy_behavior_context(
    insights: Sequence[BehaviorInsightRecord],
) -> StrategyBehaviorContext:
    """Pure adapter: confirmed insights only, stable ordering, deduplicated keys."""
    confirmed: list[ConfirmedBehaviorInsight] = []
    seen_keys: set[str] = set()
    malformed_targets = 0

    sorted_records = sorted(
        insights,
        key=lambda item: (item.insight_type, item.target_key or "", item.updated_at, item.id),
    )

    for record in sorted_records:
        if record.status != BehaviorInsightStatus.CONFIRMED.value:
            continue
        mapped = _record_to_confirmed(record)
        if mapped is None:
            continue

        dedupe_key = f"{mapped.insight_type.value}:{mapped.target_key or ''}"
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        if mapped.insight_type in {
            BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT,
            BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION,
        }:
            if not mapped.target_key or not mapped.target_key.strip():
                malformed_targets += 1
                continue

        confirmed.append(mapped)

    if malformed_targets:
        logger.info("behavior_context_malformed_targets count=%s", malformed_targets)

    frequent = tuple(
        item
        for item in confirmed
        if item.insight_type == BehaviorInsightType.FREQUENT_RECIPE_REPLACEMENT
    )
    availability = tuple(
        item
        for item in confirmed
        if item.insight_type == BehaviorInsightType.INGREDIENT_AVAILABILITY_FRICTION
    )
    high_rate = any(
        item.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE for item in confirmed
    )

    return StrategyBehaviorContext(
        frequent_recipe_replacements=frequent,
        ingredient_availability_frictions=availability,
        high_replacement_rate=high_rate,
        insights=tuple(confirmed),
    )
