"""Deterministic application of confirmed behavior insights to strategy fields."""

from __future__ import annotations

from dataclasses import dataclass

from behavior.constants import BehaviorInsightType
from shopping.normalization import canonical_ingredient_name, display_ingredient_name
from strategy.applied_behavior import (
    BEHAVIOR_AVAILABILITY_FRICTION_APPLIED,
    BEHAVIOR_HIGH_REPLACEMENT_RATE_NEEDS_USER_CHOICE,
    BEHAVIOR_INSIGHT_INVALID_TARGET,
    BEHAVIOR_RECIPE_PATTERN_NOT_ACTIONABLE,
    BEHAVIOR_REDUNDANT_WITH_HIGHER_PRIORITY,
    AppliedBehaviorDecision,
    AppliedBehaviorSnapshot,
)
from strategy.behavior_context import StrategyBehaviorContext
from strategy.context import ProfileContext
from strategy.effective_exclusions import SAFETY_SOURCES, build_profile_exclusions
from strategy.memory_context import StrategyMemoryContext


@dataclass(frozen=True)
class BehaviorApplicationResult:
    availability_avoid_products: tuple[str, ...]
    reason_codes: tuple[str, ...]
    applied_behavior: AppliedBehaviorSnapshot


def _higher_priority_canonicals(
    profile_context: ProfileContext,
    memory_context: StrategyMemoryContext,
    effective_excluded_products: list[str],
) -> set[str]:
    canonicals: set[str] = set()

    for exclusion in build_profile_exclusions(profile_context):
        canonicals.add(exclusion.canonical_value)

    for product in effective_excluded_products:
        canonical = canonical_ingredient_name(product)
        if canonical:
            canonicals.add(canonical)

    for avoided in memory_context.avoided_ingredients:
        if avoided:
            canonicals.add(avoided)

    return canonicals


def _is_safety_excluded(profile_context: ProfileContext, canonical: str) -> bool:
    for exclusion in build_profile_exclusions(profile_context):
        if exclusion.canonical_value == canonical and exclusion.source in SAFETY_SOURCES:
            return True
    return False


def apply_behavior_insights(
    *,
    profile_context: ProfileContext,
    memory_context: StrategyMemoryContext,
    behavior_context: StrategyBehaviorContext,
    effective_excluded_products: list[str],
) -> BehaviorApplicationResult:
    """Applies confirmed behavior without mutating inputs."""
    if not behavior_context.insights:
        return BehaviorApplicationResult(
            availability_avoid_products=(),
            reason_codes=(),
            applied_behavior=AppliedBehaviorSnapshot.empty(),
        )

    decisions: list[AppliedBehaviorDecision] = []
    reason_codes: list[str] = []
    higher_priority = _higher_priority_canonicals(
        profile_context,
        memory_context,
        effective_excluded_products,
    )

    availability_products: list[str] = []
    availability_seen: set[str] = set()

    for insight in behavior_context.frequent_recipe_replacements:
        decisions.append(
            AppliedBehaviorDecision(
                insight_id=insight.insight_id,
                insight_type=insight.insight_type,
                applied=False,
                reason_code=BEHAVIOR_RECIPE_PATTERN_NOT_ACTIONABLE,
                affected_fields=[],
                rule_version=insight.rule_version,
            )
        )

    if behavior_context.high_replacement_rate:
        high_rate_insight = next(
            (
                item
                for item in behavior_context.insights
                if item.insight_type == BehaviorInsightType.HIGH_REPLACEMENT_RATE
            ),
            None,
        )
        if high_rate_insight is not None:
            decisions.append(
                AppliedBehaviorDecision(
                    insight_id=high_rate_insight.insight_id,
                    insight_type=high_rate_insight.insight_type,
                    applied=False,
                    reason_code=BEHAVIOR_HIGH_REPLACEMENT_RATE_NEEDS_USER_CHOICE,
                    affected_fields=[],
                    rule_version=high_rate_insight.rule_version,
                )
            )

    for insight in behavior_context.ingredient_availability_frictions:
        target = insight.target_key
        if not target or not target.strip():
            decisions.append(
                AppliedBehaviorDecision(
                    insight_id=insight.insight_id,
                    insight_type=insight.insight_type,
                    applied=False,
                    reason_code=BEHAVIOR_INSIGHT_INVALID_TARGET,
                    affected_fields=[],
                    rule_version=insight.rule_version,
                )
            )
            continue

        canonical = canonical_ingredient_name(target)
        if not canonical:
            decisions.append(
                AppliedBehaviorDecision(
                    insight_id=insight.insight_id,
                    insight_type=insight.insight_type,
                    applied=False,
                    reason_code=BEHAVIOR_INSIGHT_INVALID_TARGET,
                    affected_fields=[],
                    rule_version=insight.rule_version,
                )
            )
            continue

        if canonical in higher_priority or _is_safety_excluded(profile_context, canonical):
            decisions.append(
                AppliedBehaviorDecision(
                    insight_id=insight.insight_id,
                    insight_type=insight.insight_type,
                    applied=False,
                    reason_code=BEHAVIOR_REDUNDANT_WITH_HIGHER_PRIORITY,
                    affected_fields=[],
                    rule_version=insight.rule_version,
                )
            )
            continue

        if canonical not in availability_seen:
            availability_seen.add(canonical)
            availability_products.append(display_ingredient_name(canonical))

        decisions.append(
            AppliedBehaviorDecision(
                insight_id=insight.insight_id,
                insight_type=insight.insight_type,
                applied=True,
                reason_code=BEHAVIOR_AVAILABILITY_FRICTION_APPLIED,
                affected_fields=["availability_avoid_products"],
                rule_version=insight.rule_version,
            )
        )

    if availability_products:
        reason_codes.append(BEHAVIOR_AVAILABILITY_FRICTION_APPLIED)

    snapshot = AppliedBehaviorSnapshot(decisions=decisions)
    return BehaviorApplicationResult(
        availability_avoid_products=tuple(availability_products),
        reason_codes=tuple(sorted(set(reason_codes))),
        applied_behavior=snapshot,
    )
