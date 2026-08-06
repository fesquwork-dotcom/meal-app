"""Builds DecisionTrace at resolution time from resolver intermediates.

The builder never re-executes rules: it receives the same intermediate results
the resolver used (memory/behavior application results, effective preferences)
and records provenance. Sensitive targets are traced as counts only.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from decision.trace_models import (
    SOURCE_PRECEDENCE,
    DecisionRuleTrace,
    DecisionSourceReference,
    DecisionTrace,
    DecisionTraceEntry,
    DecisionTraceValue,
)
from decision.versions import DECISION_TRACE_VERSION, DECISION_VERSION
from memory.constants import SignalType
from strategy.behavior_context import StrategyBehaviorContext
from strategy.context import ProfileContext
from strategy.cooking_preference import EffectiveCookingPreference
from strategy.memory_apply import MemoryApplyResult
from strategy.memory_context import StrategyMemoryContext
from decision.learned_preferences_context import LearnedPreferencesContext
from strategy.planning_preference import EffectiveFamiliarMealsPreference

logger = logging.getLogger(__name__)

# Descriptor reason codes that describe context, not a traced decision branch.
TRACE_EXEMPT_REASON_CODES: frozenset[str] = frozenset(
    {
        "GOAL_BUDGET",
        "GOAL_WEIGHT_LOSS",
        "GOAL_MUSCLE",
        "GOAL_HOME",
        "GOAL_HEALTHY",
        "GOAL_RESTAURANT",
        "LEFTOVERS_SUPPORT_BUDGET",
        "BUDGET_LIMITED_VARIETY",
        "MEAL_TYPES_CUSTOM",
        "PROTEIN_ROTATION_FOR_VARIETY",
        "EXCLUSIONS_APPLIED",
        "PROFILE_ALLERGY_CONSTRAINTS_APPLIED",
        "PROFILE_INTOLERANCE_CONSTRAINTS_APPLIED",
        "PROFILE_PREFERENCE_EXCLUSIONS_APPLIED",
        "PROFILE_LEGACY_CONSTRAINTS_APPLIED",
    }
)


def _source(
    source: str,
    *,
    field_name: str | None = None,
    applied: bool,
) -> DecisionSourceReference:
    return DecisionSourceReference(
        source=source,  # type: ignore[arg-type]
        field=field_name,
        precedence=SOURCE_PRECEDENCE[source],
        applied=applied,
    )


@dataclass(frozen=True)
class TraceBuildInputs:
    """Resolver intermediates required to record provenance without re-running rules."""

    profile_raw: dict[str, object]
    context: ProfileContext
    memory_context: StrategyMemoryContext
    behavior_context: StrategyBehaviorContext
    learned_context: LearnedPreferencesContext
    memory_result: MemoryApplyResult
    availability_avoid_count: int
    behavior_ignored_count: int
    effective_faster: EffectiveCookingPreference
    familiar_effective: EffectiveFamiliarMealsPreference
    goal: str
    days: int
    weekly_budget: float
    daily_budget: float
    base_cook_limit: int
    cook_days: list[int] = field(default_factory=list)
    shopping_days: list[int] = field(default_factory=list)
    leftovers_enabled: bool = False
    batch_allowed: bool = False
    repeat_breakfasts: bool = False
    repeat_lunches: bool = False
    repeat_dinners: bool = False


def _budget_entries(inputs: TraceBuildInputs) -> list[DecisionTraceEntry]:
    raw_budget = inputs.profile_raw.get("budget")
    budget_explicit = (
        isinstance(raw_budget, (int, float))
        and not isinstance(raw_budget, bool)
        and float(raw_budget) >= 0
    )

    weekly = DecisionTraceEntry(
        decision_key="budget.weekly",
        outcome=DecisionTraceValue.from_value(inputs.weekly_budget),
        sources=[
            _source("profile", field_name="budget", applied=budget_explicit),
            _source("default", applied=not budget_explicit),
        ],
        applied_rules=[
            DecisionRuleTrace(
                rule_code="BUDGET_WEEKLY_FROM_PROFILE"
                if budget_explicit
                else "BUDGET_WEEKLY_DEFAULT",
                result="applied",
                reason_code="BUDGET_PROFILE_VALUE_APPLIED"
                if budget_explicit
                else "BUDGET_DEFAULT_APPLIED",
                input_summary={"weekly_budget": inputs.weekly_budget},
            )
        ],
        rejected_rules=[],
        priority_winner="profile" if budget_explicit else "default",
        confidence="explicit" if budget_explicit else "fallback",
    )

    daily = DecisionTraceEntry(
        decision_key="budget.daily",
        outcome=DecisionTraceValue.from_value(inputs.daily_budget),
        sources=[_source("rule", applied=True)],
        applied_rules=[
            DecisionRuleTrace(
                rule_code="BUDGET_DAILY_DERIVED",
                result="applied",
                reason_code="BUDGET_DAILY_FROM_WEEKLY",
                input_summary={
                    "weekly_budget": inputs.weekly_budget,
                    "days": inputs.days,
                },
            )
        ],
        rejected_rules=[],
        priority_winner="rule",
        confidence="deterministic",
    )
    return [weekly, daily]


def _faster_memory_decision(inputs: TraceBuildInputs):
    for decision in inputs.memory_result.snapshot.decisions:
        if decision.signal_type == SignalType.PREFER_FASTER_MEALS.value:
            return decision
    return None


def _cooking_time_limit_entry(inputs: TraceBuildInputs) -> DecisionTraceEntry:
    final_limit = inputs.memory_result.cooking_time_limit
    downgraded = final_limit < inputs.base_cook_limit
    faster_decision = _faster_memory_decision(inputs)

    if final_limit <= 20:
        band_reason = "COOKING_TIME_LIMIT_FAST"
    elif final_limit <= 45:
        band_reason = "COOKING_TIME_LIMIT_MEDIUM"
    else:
        band_reason = "COOKING_TIME_LIMIT_SLOW"

    applied_rules = [
        DecisionRuleTrace(
            rule_code="COOKING_TIME_LIMIT_FROM_COOKTIME",
            result="applied",
            reason_code=band_reason,
            input_summary={
                "cooktime": inputs.context.cooktime,
                "cooktime_explicit": inputs.context.cooktime_is_explicit,
                "base_time_limit": inputs.base_cook_limit,
            },
        )
    ]
    rejected_rules: list[DecisionRuleTrace] = []

    if downgraded:
        applied_rules.append(
            DecisionRuleTrace(
                rule_code="MEMORY_FASTER_TIME_DOWNGRADE",
                result="applied",
                reason_code="MEMORY_FASTER_MEALS_APPLIED",
                input_summary={
                    "base_time_limit": inputs.base_cook_limit,
                    "time_limit": final_limit,
                },
            )
        )
    elif faster_decision is not None and inputs.context.cooktime_is_explicit:
        rejected_rules.append(
            DecisionRuleTrace(
                rule_code="MEMORY_FASTER_TIME_DOWNGRADE",
                result="rejected",
                reason_code="PROFILE_COOKTIME_EXPLICIT",
                input_summary={
                    "cooktime": inputs.context.cooktime,
                    "cooktime_explicit": True,
                },
            )
        )
    elif faster_decision is not None and not faster_decision.applied:
        rejected_rules.append(
            DecisionRuleTrace(
                rule_code="MEMORY_FASTER_TIME_DOWNGRADE",
                result="skipped",
                reason_code=faster_decision.reason_code,
                input_summary={"profile_value": inputs.context.prefer_faster_meals},
            )
        )

    sources = [
        _source("profile", field_name="cooktime", applied=not downgraded),
    ]
    if faster_decision is not None:
        sources.append(_source("memory", field_name="prefer_faster_meals", applied=downgraded))

    if inputs.context.cooktime_is_explicit:
        confidence = "explicit"
    elif downgraded:
        confidence = "inferred"
    else:
        confidence = "fallback"

    return DecisionTraceEntry(
        decision_key="cooking.time_limit",
        outcome=DecisionTraceValue.from_value(final_limit),
        sources=sources,
        applied_rules=applied_rules,
        rejected_rules=rejected_rules,
        priority_winner="memory" if downgraded else "profile",
        confidence=confidence,
    )


def _prefer_faster_entry(inputs: TraceBuildInputs) -> DecisionTraceEntry:
    actual = inputs.memory_result.prefer_faster_meals
    profile_value = inputs.context.prefer_faster_meals
    source_label = inputs.effective_faster.source
    faster_decision = _faster_memory_decision(inputs)

    applied_rules: list[DecisionRuleTrace] = []
    rejected_rules: list[DecisionRuleTrace] = []

    if source_label == "profile" and actual == profile_value:
        applied_rules.append(
            DecisionRuleTrace(
                rule_code="PROFILE_FASTER_PREFERENCE",
                result="applied",
                reason_code="PROFILE_FASTER_MEALS_PREFERENCE_APPLIED"
                if actual
                else "PROFILE_FASTER_MEALS_DISABLED",
                input_summary={"profile_value": profile_value},
            )
        )
    elif source_label == "memory" and actual:
        applied_rules.append(
            DecisionRuleTrace(
                rule_code="MEMORY_FASTER_PREFERENCE",
                result="applied",
                reason_code="MEMORY_FASTER_MEALS_APPLIED",
                input_summary={"memory_value": True},
            )
        )
    elif source_label == "learned_preference" and actual:
        applied_rules.append(
            DecisionRuleTrace(
                rule_code="LEARNED_FASTER_PREFERENCE",
                result="applied",
                reason_code="LEARNED_FASTER_MEALS_APPLIED",
                input_summary={"learned_value": True},
            )
        )
    else:
        # No enabling source: default disabled. Since Sprint 9.2.1 an explicit
        # profile value always resolves via the profile branch above,
        # regardless of whether Memory signals exist.
        applied_rules.append(
            DecisionRuleTrace(
                rule_code="PREFER_FASTER_NOT_ENABLED",
                result="applied",
                reason_code="PREFER_FASTER_DEFAULT_DISABLED",
                input_summary={"profile_value": profile_value},
            )
        )

    if faster_decision is not None and not faster_decision.applied:
        rejected_rules.append(
            DecisionRuleTrace(
                rule_code="MEMORY_FASTER_PREFERENCE",
                result="skipped",
                reason_code=faster_decision.reason_code,
                input_summary={"profile_value": profile_value},
            )
        )
    if (
        inputs.learned_context.prefer_faster_meals is True
        and source_label == "profile"
    ):
        rejected_rules.append(
            DecisionRuleTrace(
                rule_code="LEARNED_FASTER_PREFERENCE",
                result="skipped",
                reason_code=(
                    "LEARNED_PREFERENCE_REDUNDANT_WITH_PROFILE"
                    if profile_value is True
                    else "LEARNED_PREFERENCE_IGNORED_PROFILE_PRIORITY"
                ),
                input_summary={
                    "profile_value": profile_value,
                    "learned_value": True,
                },
            )
        )

    sources: list[DecisionSourceReference] = []
    if profile_value is not None:
        sources.append(
            _source(
                "profile",
                field_name="cooking_preferences.prefer_faster_meals",
                applied=source_label == "profile" and actual == profile_value,
            )
        )
    if inputs.learned_context.prefer_faster_meals is True:
        sources.append(
            _source(
                "learned_preference",
                field_name="prefer_fast_meals",
                applied=source_label == "learned_preference" and actual,
            )
        )
    if faster_decision is not None or inputs.memory_context.prefer_faster_meals:
        sources.append(
            _source(
                "memory",
                field_name="prefer_faster_meals",
                applied=source_label == "memory" and actual,
            )
        )
    sources.append(_source("default", applied=source_label == "default"))

    if source_label == "profile" and actual == profile_value:
        confidence = "explicit"
        winner = "profile"
    elif source_label == "memory" and actual:
        confidence = "inferred"
        winner = "memory"
    elif source_label == "learned_preference" and actual:
        confidence = "explicit"
        winner = "learned_preference"
    else:
        confidence = "fallback"
        winner = "default"

    return DecisionTraceEntry(
        decision_key="cooking.prefer_faster",
        outcome=DecisionTraceValue.from_value(actual),
        sources=sources,
        applied_rules=applied_rules,
        rejected_rules=rejected_rules,
        priority_winner=winner,
        confidence=confidence,
    )


def _cook_days_entry(inputs: TraceBuildInputs) -> DecisionTraceEntry:
    fast_mode = inputs.days <= 3 or inputs.context.cooktime == "fast"
    batch_goal = inputs.goal in {"home", "budget", "muscle"}
    all_days = list(range(1, inputs.days + 1))
    is_batch_result = inputs.cook_days != all_days

    applied_rules: list[DecisionRuleTrace] = []
    rejected_rules: list[DecisionRuleTrace] = []

    # Sprint 10.11.6 — leftovers=false forces daily cook days.
    if not inputs.leftovers_enabled and not is_batch_result:
        applied_rules.append(
            DecisionRuleTrace(
                rule_code="COOK_DAYS_DAILY_NO_LEFTOVERS",
                result="applied",
                reason_code="COOK_DAYS_DAILY_NO_LEFTOVERS",
                input_summary={
                    "goal": inputs.goal,
                    "days": inputs.days,
                    "leftovers_enabled": False,
                },
            )
        )
        if batch_goal:
            rejected_rules.append(
                DecisionRuleTrace(
                    rule_code="COOK_DAYS_BATCH_GOAL",
                    result="rejected",
                    reason_code="COOK_DAYS_REQUIRES_LEFTOVERS",
                    input_summary={"goal": inputs.goal, "leftovers_enabled": False},
                )
            )
        if fast_mode:
            rejected_rules.append(
                DecisionRuleTrace(
                    rule_code="COOK_DAYS_DAILY_FAST",
                    result="skipped",
                    reason_code="COOK_DAYS_NO_LEFTOVERS_PRIORITY",
                    input_summary={"cooktime": inputs.context.cooktime},
                )
            )
    elif fast_mode:
        applied_rules.append(
            DecisionRuleTrace(
                rule_code="COOK_DAYS_DAILY_FAST",
                result="applied",
                reason_code="COOK_DAYS_FAST_MODE",
                input_summary={"days": inputs.days, "cooktime": inputs.context.cooktime},
            )
        )
        rejected_rules.append(
            DecisionRuleTrace(
                rule_code="COOK_DAYS_BATCH_GOAL",
                result="skipped",
                reason_code="COOK_DAYS_FAST_MODE_PRIORITY",
                input_summary={"goal": inputs.goal},
            )
        )
    elif is_batch_result:
        applied_rules.append(
            DecisionRuleTrace(
                rule_code="COOK_DAYS_BATCH_GOAL",
                result="applied",
                reason_code="COOK_DAYS_REDUCE_DAILY_WORK",
                input_summary={"goal": inputs.goal, "days": inputs.days},
            )
        )
        rejected_rules.append(
            DecisionRuleTrace(
                rule_code="COOK_DAYS_DAILY_FAST",
                result="rejected",
                reason_code="PROFILE_COOKTIME_NOT_FAST",
                input_summary={"cooktime": inputs.context.cooktime, "days": inputs.days},
            )
        )
    else:
        applied_rules.append(
            DecisionRuleTrace(
                rule_code="COOK_DAYS_DAILY_VARIETY",
                result="applied",
                reason_code="COOK_DAYS_DAILY_VARIETY",
                input_summary={"goal": inputs.goal, "days": inputs.days},
            )
        )
        rejected_rules.append(
            DecisionRuleTrace(
                rule_code="COOK_DAYS_DAILY_FAST",
                result="rejected",
                reason_code="PROFILE_COOKTIME_NOT_FAST",
                input_summary={"cooktime": inputs.context.cooktime, "days": inputs.days},
            )
        )
        if not batch_goal:
            rejected_rules.append(
                DecisionRuleTrace(
                    rule_code="COOK_DAYS_BATCH_GOAL",
                    result="rejected",
                    reason_code="GOAL_NOT_BATCH_ELIGIBLE",
                    input_summary={"goal": inputs.goal},
                )
            )

    return DecisionTraceEntry(
        decision_key="cooking.cook_days",
        outcome=DecisionTraceValue.from_value(inputs.cook_days),
        sources=[_source("rule", applied=True)],
        applied_rules=applied_rules,
        rejected_rules=rejected_rules,
        priority_winner="rule",
        confidence="deterministic",
    )


def _batch_allowed_entry(inputs: TraceBuildInputs) -> DecisionTraceEntry:
    return DecisionTraceEntry(
        decision_key="cooking.batch_allowed",
        outcome=DecisionTraceValue.from_value(inputs.batch_allowed),
        sources=[_source("rule", applied=True)],
        applied_rules=[
            DecisionRuleTrace(
                rule_code="BATCH_ALLOWED_DERIVED",
                result="applied",
                reason_code="BATCH_ALLOWED_FROM_COOK_DAYS"
                if inputs.batch_allowed
                else "BATCH_NOT_ALLOWED",
                input_summary={
                    "cook_days_count": len(inputs.cook_days),
                    "days": inputs.days,
                    "leftovers_enabled": inputs.leftovers_enabled,
                },
            )
        ],
        rejected_rules=[],
        priority_winner="rule",
        confidence="deterministic",
    )


def _protein_entries(inputs: TraceBuildInputs) -> list[DecisionTraceEntry]:
    explicit = inputs.context.proteins_explicit and inputs.context.proteins != ["any"]
    preferred = list(inputs.memory_result.preferred_proteins)
    base = list(inputs.context.proteins)
    blocked_count = len([item for item in base if item not in preferred and item != "any"])

    preferred_sources = [
        _source("profile", field_name="proteins", applied=explicit),
        _source("default", applied=not explicit),
    ]
    if blocked_count:
        preferred_sources.insert(1, _source("memory", field_name="avoid_ingredient", applied=True))

    preferred_entry = DecisionTraceEntry(
        decision_key="protein.preferred",
        outcome=DecisionTraceValue.from_value(preferred),
        sources=preferred_sources,
        applied_rules=[
            DecisionRuleTrace(
                rule_code="PROTEIN_PREFERRED_FROM_PROFILE"
                if explicit
                else "PROTEIN_PREFERRED_DEFAULT_ANY",
                result="applied",
                reason_code="PROTEIN_PROFILE_VALUE_APPLIED"
                if explicit
                else "PROTEIN_DEFAULT_APPLIED",
                input_summary={
                    "proteins_explicit": explicit,
                    "preferred_count": len(preferred),
                },
            )
        ],
        rejected_rules=[],
        priority_winner="profile" if explicit else "default",
        confidence="explicit" if explicit else "fallback",
    )

    excluded_rules = [
        DecisionRuleTrace(
            rule_code="MEMORY_PROTEIN_CONFLICT_REMOVAL",
            result="applied" if blocked_count else "skipped",
            reason_code="MEMORY_PROTEIN_CONFLICT_RESOLVED"
            if blocked_count
            else "MEMORY_NO_PROTEIN_CONFLICT",
            input_summary={"blocked_count": blocked_count},
        )
    ]
    excluded_entry = DecisionTraceEntry(
        decision_key="protein.excluded",
        outcome=DecisionTraceValue.from_value(blocked_count),
        sources=[
            _source("memory", field_name="avoid_ingredient", applied=blocked_count > 0),
            _source("default", applied=blocked_count == 0),
        ],
        applied_rules=[rule for rule in excluded_rules if rule.result == "applied"],
        rejected_rules=[rule for rule in excluded_rules if rule.result != "applied"],
        priority_winner="memory" if blocked_count else "default",
        confidence="inferred" if blocked_count else "deterministic",
    )
    return [preferred_entry, excluded_entry]


def _shopping_entry(inputs: TraceBuildInputs) -> DecisionTraceEntry:
    split = len(inputs.shopping_days) > 1

    applied_rules = [
        DecisionRuleTrace(
            rule_code="SHOPPING_SPLIT_FRESH" if split else "SHOPPING_SINGLE_TRIP",
            result="applied",
            reason_code="SHOPPING_DAYS_SPLIT_FRESH_PRODUCTS"
            if split
            else "SHOPPING_DAYS_SINGLE_TRIP",
            input_summary={"goal": inputs.goal, "days": inputs.days},
        )
    ]
    rejected_rules = []
    if not split:
        rejected_rules.append(
            DecisionRuleTrace(
                rule_code="SHOPPING_SPLIT_FRESH",
                result="rejected",
                reason_code="GOAL_NOT_BUDGET"
                if inputs.goal != "budget"
                else "DAYS_BELOW_SPLIT_THRESHOLD",
                input_summary={"goal": inputs.goal, "days": inputs.days},
            )
        )

    return DecisionTraceEntry(
        decision_key="shopping.days",
        outcome=DecisionTraceValue.from_value(inputs.shopping_days),
        sources=[_source("rule", applied=True)],
        applied_rules=applied_rules,
        rejected_rules=rejected_rules,
        priority_winner="rule",
        confidence="deterministic",
    )


def _meal_boolean_entry(
    decision_key: str,
    value: bool,
    *,
    applied_reason: str,
    disabled_reason: str,
    rule_code: str,
    inputs: TraceBuildInputs,
) -> DecisionTraceEntry:
    return DecisionTraceEntry(
        decision_key=decision_key,
        outcome=DecisionTraceValue.from_value(value),
        sources=[_source("rule", applied=True)],
        applied_rules=[
            DecisionRuleTrace(
                rule_code=rule_code,
                result="applied",
                reason_code=applied_reason if value else disabled_reason,
                input_summary={"goal": inputs.goal, "days": inputs.days},
            )
        ],
        rejected_rules=[],
        priority_winner="rule",
        confidence="deterministic",
    )


def _exclusions_entry(inputs: TraceBuildInputs) -> list[DecisionTraceEntry]:
    # Values live in DecisionContext/WeeklyStrategy; trace records counts only.
    avoid_decisions = [
        decision
        for decision in inputs.memory_result.snapshot.decisions
        if decision.signal_type == SignalType.AVOID_INGREDIENT.value
    ]
    counts_by_reason: dict[str, int] = {}
    applied_by_reason: dict[str, bool] = {}
    for decision in avoid_decisions:
        counts_by_reason[decision.reason_code] = counts_by_reason.get(decision.reason_code, 0) + 1
        applied_by_reason[decision.reason_code] = decision.applied

    applied_rules: list[DecisionRuleTrace] = []
    rejected_rules: list[DecisionRuleTrace] = []
    for reason_code in sorted(counts_by_reason):
        rule = DecisionRuleTrace(
            rule_code="MEMORY_AVOID_EXCLUSION",
            result="applied" if applied_by_reason[reason_code] else "rejected",
            reason_code=reason_code,
            input_summary={"avoid_count": counts_by_reason[reason_code]},
        )
        if applied_by_reason[reason_code]:
            applied_rules.append(rule)
        else:
            rejected_rules.append(rule)

    exclusion_count = len(inputs.memory_result.excluded_products)
    memory_avoid_count = len(inputs.memory_result.snapshot.avoided_ingredients)

    entry = DecisionTraceEntry(
        decision_key="exclusions.count",
        outcome=DecisionTraceValue.from_value(exclusion_count),
        sources=[
            _source("profile", field_name="dietary_constraints", applied=exclusion_count > memory_avoid_count),
            _source("memory", field_name="avoid_ingredient", applied=memory_avoid_count > 0),
            _source("default", applied=exclusion_count == 0),
        ],
        applied_rules=applied_rules,
        rejected_rules=rejected_rules,
        priority_winner="profile" if exclusion_count > memory_avoid_count else (
            "memory" if memory_avoid_count else "default"
        ),
        confidence="deterministic",
    )
    return [entry]


def _behavior_entry(inputs: TraceBuildInputs) -> DecisionTraceEntry:
    applied_count = inputs.availability_avoid_count
    ignored_count = inputs.behavior_ignored_count

    applied_rules: list[DecisionRuleTrace] = []
    rejected_rules: list[DecisionRuleTrace] = []
    if applied_count:
        applied_rules.append(
            DecisionRuleTrace(
                rule_code="BEHAVIOR_AVAILABILITY_FRICTION",
                result="applied",
                reason_code="BEHAVIOR_AVAILABILITY_FRICTION_APPLIED",
                input_summary={"avoid_count": applied_count},
            )
        )
    if ignored_count:
        rejected_rules.append(
            DecisionRuleTrace(
                rule_code="BEHAVIOR_AVAILABILITY_FRICTION",
                result="skipped",
                reason_code="BEHAVIOR_REDUNDANT_WITH_HIGHER_PRIORITY",
                input_summary={"ignored_count": ignored_count},
            )
        )

    return DecisionTraceEntry(
        decision_key="behavior.availability_avoid_products",
        outcome=DecisionTraceValue.from_value(applied_count),
        sources=[
            _source("behavior", field_name="availability_friction", applied=applied_count > 0),
            _source("default", applied=applied_count == 0),
        ],
        applied_rules=applied_rules,
        rejected_rules=rejected_rules,
        priority_winner="behavior" if applied_count else "default",
        confidence="inferred" if applied_count else "fallback",
    )


def _familiar_entry(inputs: TraceBuildInputs) -> DecisionTraceEntry:
    effective = inputs.familiar_effective
    explicit = effective.profile_value is not None
    learned = inputs.learned_context.prefer_familiar_meals is True

    if explicit:
        applied_rule = DecisionRuleTrace(
            rule_code="PROFILE_FAMILIAR_PREFERENCE",
            result="applied",
            reason_code=(
                "PROFILE_FAMILIAR_MEALS_PREFERENCE_APPLIED"
                if effective.profile_value
                else "PROFILE_FAMILIAR_MEALS_PREFERENCE_DISABLED"
            ),
            input_summary={"profile_value": effective.profile_value},
        )
    elif learned:
        applied_rule = DecisionRuleTrace(
            rule_code="LEARNED_FAMILIAR_PREFERENCE",
            result="applied",
            reason_code="LEARNED_FAMILIAR_MEALS_APPLIED",
            input_summary={"learned_value": True},
        )
    else:
        applied_rule = DecisionRuleTrace(
            rule_code="PLANNING_FAMILIAR_DEFAULT",
            result="applied",
            reason_code="PLANNING_FAMILIAR_DEFAULT_DISABLED",
            input_summary={"profile_value": None},
        )
    rejected_rules: list[DecisionRuleTrace] = []
    if learned and explicit:
        rejected_rules.append(
            DecisionRuleTrace(
                rule_code="LEARNED_FAMILIAR_PREFERENCE",
                result="skipped",
                reason_code=(
                    "LEARNED_PREFERENCE_REDUNDANT_WITH_PROFILE"
                    if effective.profile_value is True
                    else "LEARNED_PREFERENCE_IGNORED_PROFILE_PRIORITY"
                ),
                input_summary={
                    "profile_value": effective.profile_value,
                    "learned_value": True,
                },
            )
        )

    return DecisionTraceEntry(
        decision_key="planning.prefer_familiar_meals",
        outcome=DecisionTraceValue.from_value(effective.prefer_familiar_meals),
        sources=[
            _source(
                "profile",
                field_name="planning_preferences.prefer_familiar_meals",
                applied=explicit,
            ),
            *(
                [
                    _source(
                        "learned_preference",
                        field_name="prefer_familiar_meals",
                        applied=learned and not explicit,
                    )
                ]
                if learned
                else []
            ),
            _source("default", applied=not explicit and not learned),
        ],
        applied_rules=[applied_rule],
        rejected_rules=rejected_rules,
        priority_winner=(
            "profile"
            if explicit
            else ("learned_preference" if learned else "default")
        ),
        confidence="explicit" if explicit or learned else "fallback",
    )


def build_decision_trace(inputs: TraceBuildInputs) -> DecisionTrace:
    """Assembles the full trace in stable key order."""
    started = time.perf_counter()

    entries: list[DecisionTraceEntry] = []
    entries.extend(_budget_entries(inputs))
    entries.append(_cooking_time_limit_entry(inputs))
    entries.append(_prefer_faster_entry(inputs))
    entries.append(_cook_days_entry(inputs))
    entries.append(_batch_allowed_entry(inputs))
    entries.extend(_protein_entries(inputs))
    entries.append(_shopping_entry(inputs))
    entries.append(
        _meal_boolean_entry(
            "meal.leftovers_enabled",
            inputs.leftovers_enabled,
            applied_reason="LEFTOVERS_REDUCE_COOKING",
            disabled_reason="LEFTOVERS_GOAL_NOT_ELIGIBLE",
            rule_code="LEFTOVERS_GOAL_RULE",
            inputs=inputs,
        )
    )
    entries.append(
        _meal_boolean_entry(
            "meal.repeat_breakfasts",
            inputs.repeat_breakfasts,
            applied_reason="REPEAT_BREAKFASTS_SAVE_TIME",
            disabled_reason="REPEAT_BREAKFASTS_NOT_ELIGIBLE",
            rule_code="REPEAT_BREAKFASTS_GOAL_RULE",
            inputs=inputs,
        )
    )
    entries.append(
        _meal_boolean_entry(
            "meal.repeat_lunches",
            inputs.repeat_lunches,
            applied_reason="REPEAT_LUNCHES_SUPPORT_BATCH",
            disabled_reason="REPEAT_LUNCHES_NOT_ELIGIBLE",
            rule_code="REPEAT_LUNCHES_GOAL_RULE",
            inputs=inputs,
        )
    )
    entries.append(
        _meal_boolean_entry(
            "meal.repeat_dinners",
            inputs.repeat_dinners,
            applied_reason="REPEAT_DINNERS_SUPPORT_BUDGET",
            disabled_reason="REPEAT_DINNERS_NOT_ELIGIBLE",
            rule_code="REPEAT_DINNERS_GOAL_RULE",
            inputs=inputs,
        )
    )
    entries.extend(_exclusions_entry(inputs))
    entries.append(_behavior_entry(inputs))
    entries.append(_familiar_entry(inputs))

    trace = DecisionTrace(
        trace_version=DECISION_TRACE_VERSION,
        decision_version=DECISION_VERSION,
        entries=entries,
    )

    applied_total = sum(len(entry.applied_rules) for entry in trace.entries)
    rejected_total = sum(len(entry.rejected_rules) for entry in trace.entries)
    logger.info(
        "decision_trace_built trace_version=%s decision_count=%s applied_rule_count=%s "
        "rejected_rule_count=%s duration_ms=%s",
        trace.trace_version,
        len(trace.entries),
        applied_total,
        rejected_total,
        int((time.perf_counter() - started) * 1000),
    )
    return trace


def find_trace_consistency_issues(
    trace: DecisionTrace,
    reason_codes: list[str] | tuple[str, ...],
) -> list[str]:
    """Every non-exempt recorded reason code must appear in the trace rules.

    The trace may contain more technical rules than user-facing explanation.
    """
    issues: list[str] = []

    trace_reason_codes: set[str] = set()
    seen_keys: set[str] = set()
    for entry in trace.entries:
        if entry.decision_key in seen_keys:
            issues.append(f"duplicate_decision_key:{entry.decision_key}")
        seen_keys.add(entry.decision_key)
        if entry.priority_winner is not None and entry.priority_winner not in {
            source.source for source in entry.sources
        } | {"rule"}:
            issues.append(f"winner_not_in_sources:{entry.decision_key}")
        for rule in list(entry.applied_rules) + list(entry.rejected_rules):
            trace_reason_codes.add(rule.reason_code)

    for code in reason_codes:
        if code in TRACE_EXEMPT_REASON_CODES:
            continue
        if code not in trace_reason_codes:
            issues.append(f"reason_code_without_trace_rule:{code}")

    if issues:
        logger.warning(
            "decision_trace_consistency_failed issue_count=%s first=%s",
            len(issues),
            issues[0],
        )
    return issues
