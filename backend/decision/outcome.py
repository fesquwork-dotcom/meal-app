"""Deterministic retrospective evaluation of persisted decisions.

Outcomes are observational only. Nothing in this module is imported by the
Decision Engine or used to alter future decisions.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from decision.trace_models import DecisionTrace, DecisionTraceEntry
from decision.versions import DECISION_OUTCOME_VERSION
from memory.constants import MemoryEventType, ReplacementReasonCode
from memory.records import MemoryEventRecord

if TYPE_CHECKING:
    from menu_models import MenuPlan
    from strategy.models import WeeklyStrategy

logger = logging.getLogger(__name__)

OutcomeStatus = Literal[
    "pending",
    "successful",
    "neutral",
    "unsuccessful",
    "insufficient_data",
]
OutcomeConfidence = Literal["strong", "moderate", "limited"]

SUPPORTED_DECISION_KEYS = frozenset(
    {
        "planning.prefer_familiar_meals",
        "cooking.prefer_faster",
        "behavior.availability_avoid_products",
        "cooking.cook_days",
        "shopping.days",
    }
)


class DecisionOutcome(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    decision_key: str = Field(max_length=80)
    result: str = Field(max_length=80)
    confidence: OutcomeConfidence
    evidence_count: int = Field(ge=0)
    status: OutcomeStatus


class DecisionFeedback(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    decision_key: str = Field(max_length=80)
    feedback: str = Field(max_length=160)
    recommendation: str = Field(max_length=200)
    confidence: OutcomeConfidence
    source: Literal["decision_outcome"] = "decision_outcome"


class DecisionOutcomeCollection(BaseModel):
    model_config = ConfigDict(frozen=True, extra="ignore")

    version: int = DECISION_OUTCOME_VERSION
    outcomes: list[DecisionOutcome] = Field(default_factory=list)
    feedback: list[DecisionFeedback] = Field(default_factory=list)

    def to_json(self) -> str:
        return self.model_dump_json()

    @classmethod
    def from_json(cls, raw: str | None) -> "DecisionOutcomeCollection | None":
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("decision_outcomes_unavailable reason=malformed_json")
            return None
        if not isinstance(parsed, dict):
            logger.warning("decision_outcomes_unavailable reason=not_object")
            return None
        if parsed.get("version") != DECISION_OUTCOME_VERSION:
            logger.warning(
                "decision_outcomes_unavailable reason=unsupported_version version=%s",
                parsed.get("version"),
            )
            return None
        try:
            return cls.model_validate(parsed)
        except ValueError:
            logger.warning("decision_outcomes_unavailable reason=invalid_payload")
            return None


class OutcomeExplanation(BaseModel):
    """Public, aggregate-only retrospective text."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    decision_key: str = Field(max_length=80)
    title: str = Field(max_length=80)
    status: OutcomeStatus
    status_label: str = Field(max_length=80)
    explanation: str = Field(max_length=300)


class DecisionOutcomeSummary(BaseModel):
    """Safe API projection; raw evidence and evaluator result codes are omitted."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    version: int = DECISION_OUTCOME_VERSION
    evaluated_count: int = Field(ge=0)
    successful_count: int = Field(ge=0)
    neutral_count: int = Field(ge=0)
    unsuccessful_count: int = Field(ge=0)
    insufficient_data_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    explanations: list[OutcomeExplanation] = Field(default_factory=list, max_length=5)


def _event_count(events: Sequence[MemoryEventRecord]) -> int:
    distinct: set[str] = set()
    for event in events:
        distinct.add(event.meal_id or event.event_key)
    return len(distinct)


@dataclass(frozen=True)
class PositiveEvidence:
    """Sprint 6.5 — aggregated explicit success events for one strategy."""

    cooked_meal_count: int = 0
    suited_meal_count: int = 0
    shopping_completed: bool = False
    plan_completed: bool = False


def _collect_positive_evidence(
    memory_events: Sequence[MemoryEventRecord],
) -> PositiveEvidence:
    by_type: dict[str, list[MemoryEventRecord]] = {}
    for event in memory_events:
        by_type.setdefault(event.event_type, []).append(event)
    return PositiveEvidence(
        cooked_meal_count=_event_count(
            by_type.get(MemoryEventType.MEAL_COOKED.value, [])
        ),
        suited_meal_count=_event_count(
            by_type.get(MemoryEventType.MEAL_SUITED.value, [])
        ),
        shopping_completed=bool(
            by_type.get(MemoryEventType.SHOPPING_COMPLETED.value)
        ),
        plan_completed=bool(by_type.get(MemoryEventType.PLAN_COMPLETED.value)),
    )


def _planned_meal_count(strategy: WeeklyStrategy, menu_plan: MenuPlan | None) -> int:
    if menu_plan is not None and hasattr(menu_plan, "days_plan"):
        count = sum(len(day.meals) for day in menu_plan.days_plan)
        if count > 0:
            return count
    return strategy.days * strategy.meals_per_day


def _status_from_rate(rate: float) -> tuple[OutcomeStatus, str, OutcomeConfidence]:
    if rate <= 0.10:
        return "successful", "low_replacement_rate", "moderate"
    if rate <= 0.35:
        return "neutral", "moderate_replacement_rate", "moderate"
    return "unsuccessful", "high_replacement_rate", "strong"


def _positive_only_outcome(
    decision_key: str, positive: PositiveEvidence
) -> DecisionOutcome | None:
    """Success proven by explicit user marks when no replacements happened.

    Single marks stay below the evidence threshold on purpose: one event does
    not prove a weekly decision worked.
    """
    if decision_key == "shopping.days" and positive.shopping_completed:
        return DecisionOutcome(
            decision_key=decision_key,
            result="shopping_completed_confirmed",
            confidence="moderate",
            evidence_count=1,
            status="successful",
        )
    if (
        decision_key == "behavior.availability_avoid_products"
        and positive.shopping_completed
    ):
        return DecisionOutcome(
            decision_key=decision_key,
            result="no_availability_friction_confirmed",
            confidence="moderate",
            evidence_count=1,
            status="successful",
        )
    if decision_key == "cooking.cook_days":
        if positive.cooked_meal_count >= 2:
            return DecisionOutcome(
                decision_key=decision_key,
                result="meals_cooked_as_planned",
                confidence="strong" if positive.plan_completed else "moderate",
                evidence_count=positive.cooked_meal_count,
                status="successful",
            )
        if positive.plan_completed:
            return DecisionOutcome(
                decision_key=decision_key,
                result="plan_completed_as_planned",
                confidence="moderate",
                evidence_count=1,
                status="successful",
            )
    if decision_key in {"planning.prefer_familiar_meals", "cooking.prefer_faster"}:
        if positive.suited_meal_count >= 2:
            return DecisionOutcome(
                decision_key=decision_key,
                result="meals_suited_confirmed",
                confidence="strong" if positive.suited_meal_count >= 3 else "moderate",
                evidence_count=positive.suited_meal_count,
                status="successful",
            )
        if positive.plan_completed:
            return DecisionOutcome(
                decision_key=decision_key,
                result="plan_completed_without_replacements",
                confidence="moderate",
                evidence_count=1,
                status="successful",
            )
    return None


def _has_corroborating_evidence(decision_key: str, positive: PositiveEvidence) -> bool:
    if positive.plan_completed:
        return True
    if decision_key in {"planning.prefer_familiar_meals", "cooking.prefer_faster"}:
        return positive.suited_meal_count >= 2
    if decision_key == "cooking.cook_days":
        return positive.cooked_meal_count >= 2
    if decision_key in {"shopping.days", "behavior.availability_avoid_products"}:
        return positive.shopping_completed
    return False


def _supported_outcome(
    entry: DecisionTraceEntry,
    *,
    events: Sequence[MemoryEventRecord],
    positive: PositiveEvidence,
    planned_meals: int,
) -> DecisionOutcome:
    replacement_count = _event_count(events)
    if planned_meals <= 0 or replacement_count == 0:
        confirmed = _positive_only_outcome(entry.decision_key, positive)
        if confirmed is not None and planned_meals > 0:
            return confirmed
        # Without replacements or explicit positive marks there is no proof
        # that meals were accepted or consumed.
        return DecisionOutcome(
            decision_key=entry.decision_key,
            result="no_observed_feedback",
            confidence="limited",
            evidence_count=0,
            status="insufficient_data",
        )

    replacement_rate = min(1.0, replacement_count / planned_meals)
    unavailable_events = [
        event
        for event in events
        if event.reason_code == ReplacementReasonCode.INGREDIENT_UNAVAILABLE.value
    ]
    faster_events = [
        event
        for event in events
        if event.reason_code == ReplacementReasonCode.FASTER.value
    ]

    if entry.decision_key == "behavior.availability_avoid_products":
        unavailable_count = _event_count(unavailable_events)
        if unavailable_count == 0:
            status, result, confidence = (
                "successful",
                "no_availability_replacements",
                "moderate",
            )
        elif unavailable_count / planned_meals > 0.10:
            status, result, confidence = (
                "unsuccessful",
                "availability_replacements_persisted",
                "strong",
            )
        else:
            status, result, confidence = (
                "neutral",
                "limited_availability_replacements",
                "moderate",
            )
        evidence_count = unavailable_count
    elif entry.decision_key == "shopping.days":
        unavailable_count = _event_count(unavailable_events)
        if unavailable_count == 0:
            status, result, confidence = (
                "successful",
                "no_shopping_availability_friction",
                "moderate",
            )
        elif unavailable_count / planned_meals > 0.10:
            status, result, confidence = (
                "unsuccessful",
                "shopping_availability_friction",
                "strong",
            )
        else:
            status, result, confidence = (
                "neutral",
                "limited_shopping_friction",
                "moderate",
            )
        evidence_count = unavailable_count
    elif entry.decision_key == "cooking.prefer_faster" and _event_count(faster_events) >= 2:
        status, result, confidence = (
            "unsuccessful",
            "faster_replacements_persisted",
            "strong",
        )
        evidence_count = _event_count(faster_events)
    else:
        status, result, confidence = _status_from_rate(replacement_rate)
        evidence_count = replacement_count

    if (
        status == "successful"
        and confidence == "moderate"
        and _has_corroborating_evidence(entry.decision_key, positive)
    ):
        # Replacement-based conclusion is corroborated by explicit user marks.
        confidence = "strong"

    return DecisionOutcome(
        decision_key=entry.decision_key,
        result=result,
        confidence=confidence,
        evidence_count=evidence_count,
        status=status,
    )


def _feedback_for_outcome(outcome: DecisionOutcome) -> DecisionFeedback:
    if outcome.status == "successful":
        feedback = "Решение показало хороший результат."
        recommendation = "Сохранить результат как наблюдение без изменения планировщика."
    elif outcome.status == "unsuccessful":
        feedback = "Решение часто сопровождалось заменами."
        recommendation = "Отметить решение для будущего пользовательского анализа."
    elif outcome.status == "neutral":
        feedback = "Результат решения оказался смешанным."
        recommendation = "Продолжить наблюдение без автоматических изменений."
    else:
        feedback = "Для оценки решения пока недостаточно данных."
        recommendation = "Накопить больше подтверждённых действий пользователя."
    return DecisionFeedback(
        decision_key=outcome.decision_key,
        feedback=feedback,
        recommendation=recommendation,
        confidence=outcome.confidence,
    )


def evaluate_decision_outcomes(
    trace: DecisionTrace,
    memory_events: Sequence[MemoryEventRecord],
    *,
    strategy: WeeklyStrategy,
    behavior: Sequence[object] = (),
    menu_plan: MenuPlan | None = None,
) -> DecisionOutcomeCollection:
    """Evaluate outcomes from one immutable trace and strategy-scoped events."""
    del behavior  # Reserved input: current rules need raw event records only.
    events = sorted(
        (
            event
            for event in memory_events
            if event.event_type == MemoryEventType.MEAL_REPLACED.value
        ),
        key=lambda event: (event.created_at, event.event_key),
    )
    positive = _collect_positive_evidence(memory_events)
    planned_meals = _planned_meal_count(strategy, menu_plan)
    outcomes: list[DecisionOutcome] = []

    for entry in trace.entries:
        if entry.decision_key not in SUPPORTED_DECISION_KEYS:
            outcomes.append(
                DecisionOutcome(
                    decision_key=entry.decision_key,
                    result="evaluation_not_supported",
                    confidence="limited",
                    evidence_count=0,
                    status="pending",
                )
            )
            continue
        outcomes.append(
            _supported_outcome(
                entry,
                events=events,
                positive=positive,
                planned_meals=planned_meals,
            )
        )

    feedback = [_feedback_for_outcome(outcome) for outcome in outcomes]
    collection = DecisionOutcomeCollection(outcomes=outcomes, feedback=feedback)
    status_counts = {
        status: sum(1 for item in outcomes if item.status == status)
        for status in (
            "pending",
            "successful",
            "neutral",
            "unsuccessful",
            "insufficient_data",
        )
    }
    logger.info(
        "decision_outcomes_evaluated outcome_count=%s status_counts=%s",
        len(outcomes),
        status_counts,
    )
    if (
        positive.cooked_meal_count
        or positive.suited_meal_count
        or positive.shopping_completed
        or positive.plan_completed
    ):
        logger.info(
            "decision_outcome_positive_evidence cooked=%s suited=%s "
            "shopping_completed=%s plan_completed=%s",
            positive.cooked_meal_count,
            positive.suited_meal_count,
            positive.shopping_completed,
            positive.plan_completed,
        )
    logger.info(
        "decision_feedback_generated feedback_count=%s",
        len(feedback),
    )
    event_suffix = {
        "pending": "pending",
        "successful": "success",
        "unsuccessful": "unsuccessful",
    }
    for status, suffix in event_suffix.items():
        count = status_counts[status]
        if count:
            logger.info("decision_outcome_%s count=%s", suffix, count)
    return collection


OUTCOME_TITLES = {
    "planning.prefer_familiar_meals": "Знакомые блюда",
    "cooking.prefer_faster": "Быстрые блюда",
    "behavior.availability_avoid_products": "Доступность продуктов",
    "cooking.cook_days": "Распределение готовки",
    "shopping.days": "Дни закупок",
}

STATUS_LABELS = {
    "successful": "Решение сработало хорошо",
    "neutral": "Результат оказался смешанным",
    "unsuccessful": "Решение требует внимания",
    "insufficient_data": "Пока недостаточно данных",
    "pending": "Оценка появится позже",
}


# Results proven by explicit positive marks rather than absence of replacements.
POSITIVE_CONFIRMED_RESULTS = frozenset(
    {
        "shopping_completed_confirmed",
        "no_availability_friction_confirmed",
        "meals_cooked_as_planned",
        "plan_completed_as_planned",
        "meals_suited_confirmed",
        "plan_completed_without_replacements",
    }
)


def build_outcome_summary(collection: DecisionOutcomeCollection) -> DecisionOutcomeSummary:
    explanations: list[OutcomeExplanation] = []
    for outcome in collection.outcomes:
        title = OUTCOME_TITLES.get(outcome.decision_key)
        if title is None:
            continue
        if outcome.status == "successful" and outcome.result in POSITIVE_CONFIRMED_RESULTS:
            text = "Ваши отметки подтвердили: решение сработало."
        elif outcome.status == "successful":
            text = "Большинство решений этой недели не потребовало замен по этой причине."
        elif outcome.status == "unsuccessful":
            text = "В течение недели это решение часто сопровождалось заменами."
        elif outcome.status == "neutral":
            text = "За неделю были отдельные замены, но устойчивого результата пока нет."
        elif outcome.status == "insufficient_data":
            text = "Подтверждённых действий пока недостаточно для надёжной оценки."
        else:
            text = "Оценка станет доступна после завершения периода плана."
        explanations.append(
            OutcomeExplanation(
                decision_key=outcome.decision_key,
                title=title,
                status=outcome.status,
                status_label=STATUS_LABELS[outcome.status],
                explanation=text,
            )
        )

    statuses = [item.status for item in collection.outcomes]
    return DecisionOutcomeSummary(
        evaluated_count=sum(status not in {"pending"} for status in statuses),
        successful_count=statuses.count("successful"),
        neutral_count=statuses.count("neutral"),
        unsuccessful_count=statuses.count("unsuccessful"),
        insufficient_data_count=statuses.count("insufficient_data"),
        pending_count=statuses.count("pending"),
        explanations=explanations[:5],
    )
