"""Pure Learned Preference effectiveness evaluator (Sprint 9.3).

Deterministic, I/O-free, no clocks, no LLM, no mutation of inputs.
"""

from __future__ import annotations

from collections.abc import Sequence

from learned_preferences.effectiveness_models import (
    LEARNED_PREFERENCE_EFFECTIVENESS_VERSION,
    REVIEW_COHORT_SIZE,
    LearnedPreferenceEffectiveness,
    LearnedPreferenceEffectivenessLimitation,
    LearnedPreferencePlanObservation,
)
from learned_preferences.models import LearnedPreferenceType

_SUPPORTED: frozenset[str] = frozenset(
    {"prefer_familiar_meals", "prefer_fast_meals"}
)

# Alignment with Learning enable rules: high replacement burden.
_HIGH_REPLACEMENT_RATE = 0.35
_LOW_REPLACEMENT_RATE = 0.20


def effectiveness_generation(evidence_plans: int) -> int:
    """Cohort index from applied completed plans. Pure and deterministic."""
    if evidence_plans <= 0:
        return 0
    return evidence_plans // REVIEW_COHORT_SIZE


def _confidence(applied_plans: int) -> str:
    if applied_plans <= 1:
        return "insufficient"
    if applied_plans <= 3:
        return "partial"
    return "established"


def _replacement_rate(observation: LearnedPreferencePlanObservation) -> float | None:
    planned = observation.planned_meal_count
    replacements = observation.replacement_count
    if planned is None or planned <= 0 or replacements is None:
        return None
    return min(1.0, replacements / planned)


def _is_high_replacement(observation: LearnedPreferencePlanObservation) -> bool:
    rate = _replacement_rate(observation)
    return rate is not None and rate > _HIGH_REPLACEMENT_RATE


def _is_low_replacement(observation: LearnedPreferencePlanObservation) -> bool:
    rate = _replacement_rate(observation)
    if rate is None:
        return observation.replacement_count == 0
    return rate <= _LOW_REPLACEMENT_RATE


def _classify_plan(
    preference_type: LearnedPreferenceType,
    observation: LearnedPreferencePlanObservation,
) -> str:
    """Return 'positive', 'negative', or 'neither' for one applied plan."""
    if not observation.preference_applied:
        return "neither"

    outcome = observation.decision_outcome
    high_repl = _is_high_replacement(observation)
    low_repl = _is_low_replacement(observation)

    # Unsuccessful outcome or high replacement burden is negative and cannot
    # be masked by a single plan_completed / suited mark.
    if outcome == "unsuccessful" or high_repl:
        return "negative"

    positive = False
    if outcome == "successful":
        positive = True
    elif observation.meal_suited_count >= 2 and low_repl:
        positive = True
    elif (
        preference_type == "prefer_fast_meals"
        and observation.meal_cooked_count >= 1
        and observation.meal_suited_count >= 1
        and low_repl
    ):
        positive = True
    elif observation.plan_completed and low_repl and outcome != "neutral":
        # plan_completed alone is weak; only count when replacements are low
        # and outcome is not already marked neutral.
        positive = True

    if positive:
        return "positive"
    # Absence of positive marks is not negative evidence.
    return "neither"


def evaluate_learned_preference_effectiveness(
    preference_type: LearnedPreferenceType,
    observations: Sequence[LearnedPreferencePlanObservation],
) -> LearnedPreferenceEffectiveness:
    limitations: list[LearnedPreferenceEffectivenessLimitation] = [
        "NO_CONTROL_GROUP",
        "ABSENT_POSITIVE_NOT_NEGATIVE",
    ]

    if preference_type not in _SUPPORTED:
        return LearnedPreferenceEffectiveness(
            version=LEARNED_PREFERENCE_EFFECTIVENESS_VERSION,
            preference_type=preference_type,
            status="insufficient_data",
            evidence_plans=0,
            applied_plans=0,
            positive_evidence_count=0,
            negative_evidence_count=0,
            confidence="insufficient",
            summary_code="UNSUPPORTED_TYPE",
            limitations=["UNSUPPORTED_TYPE", "NO_CONTROL_GROUP"],
            generation=0,
        )

    applied = [
        item
        for item in observations
        if item.preference_applied
    ]
    # Stable chronological order for deterministic counting.
    applied = sorted(applied, key=lambda item: item.plan_date)
    applied_plans = len(applied)
    generation = effectiveness_generation(applied_plans)
    confidence = _confidence(applied_plans)

    if applied_plans == 0:
        limitations.append("LEGACY_SNAPSHOTS_EXCLUDED")

    positive = 0
    negative = 0
    for item in applied:
        label = _classify_plan(preference_type, item)
        if label == "positive":
            positive += 1
        elif label == "negative":
            negative += 1

    if positive > 0 and negative > 0:
        limitations.append("MIXED_EVIDENCE")
    if confidence == "partial":
        limitations.append("SMALL_SAMPLE")

    # Deduplicate limitations while preserving order.
    seen: set[str] = set()
    unique_limitations: list[LearnedPreferenceEffectivenessLimitation] = []
    for item in limitations:
        if item not in seen:
            seen.add(item)
            unique_limitations.append(item)

    if confidence == "insufficient":
        return LearnedPreferenceEffectiveness(
            preference_type=preference_type,
            status="insufficient_data",
            evidence_plans=applied_plans,
            applied_plans=applied_plans,
            positive_evidence_count=positive,
            negative_evidence_count=negative,
            confidence="insufficient",
            summary_code="INSUFFICIENT_DATA",
            limitations=unique_limitations,
            generation=generation,
        )

    if confidence == "partial":
        # Strong conclusions forbidden on a small sample.
        if positive > negative:
            status = "emerging"
            summary = "EMERGING_POSITIVE"
        else:
            status = "neutral"
            summary = "NEUTRAL_MIXED"
        return LearnedPreferenceEffectiveness(
            preference_type=preference_type,
            status=status,  # type: ignore[arg-type]
            evidence_plans=applied_plans,
            applied_plans=applied_plans,
            positive_evidence_count=positive,
            negative_evidence_count=negative,
            confidence="partial",
            summary_code=summary,  # type: ignore[arg-type]
            limitations=unique_limitations,
            generation=generation,
        )

    # established: 4+
    if positive > negative:
        status = "effective"
        summary = "EFFECTIVE_STABLE"
    elif negative > positive:
        status = "ineffective"
        summary = "INEFFECTIVE_REPLACEMENTS"
    else:
        status = "neutral"
        summary = "NEUTRAL_MIXED"

    return LearnedPreferenceEffectiveness(
        preference_type=preference_type,
        status=status,  # type: ignore[arg-type]
        evidence_plans=applied_plans,
        applied_plans=applied_plans,
        positive_evidence_count=positive,
        negative_evidence_count=negative,
        confidence="established",
        summary_code=summary,  # type: ignore[arg-type]
        limitations=unique_limitations,
        generation=generation,
    )
