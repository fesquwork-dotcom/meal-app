"""Coordinates weekly strategy persistence lifecycle."""

from __future__ import annotations

import logging
from datetime import date

from decision.context import DecisionContext
from decision.outcome import (
    DecisionOutcomeSummary,
    build_outcome_summary,
    evaluate_decision_outcomes,
)
from decision.trace_models import DecisionTrace
from decision.user_explanation import (
    DecisionExplanationCollection,
    build_decision_explanations,
    build_legacy_decision_explanations,
)
from strategy.applied_behavior import AppliedBehaviorSnapshot
from strategy.applied_planning import AppliedPlanningPreferences
from strategy.applied_cooking import AppliedCookingPreference
from strategy.applied_learned_preferences import AppliedLearnedPreferencesSnapshot
from strategy.applied_settings import build_applied_settings_response
from strategy.exceptions import StrategyNotFoundError, StrategyPersistenceError
from strategy.explanation import StrategyExplanation, build_strategy_explanation
from strategy.lifecycle import is_strategy_completed, plan_end_date
from strategy.memory_context import AppliedMemorySnapshot
from strategy.models import WeeklyStrategy
from strategy.records import StrategyRecord, StrategyStatus
from strategy.repository import StrategyRepository
from memory.repository import MemoryRepository

logger = logging.getLogger(__name__)


class StrategyService:
    def __init__(
        self,
        repository: StrategyRepository | None = None,
        memory_repository: MemoryRepository | None = None,
    ) -> None:
        self._repository = repository or StrategyRepository()
        self._memory_repository = memory_repository or MemoryRepository()

    async def save_active_strategy(
        self,
        *,
        user_id: int,
        strategy: WeeklyStrategy,
        plan_start_date: date,
        reason_codes: list[str] | None = None,
        applied_memory: AppliedMemorySnapshot | None = None,
        applied_cooking_preference: AppliedCookingPreference | None = None,
        applied_behavior: AppliedBehaviorSnapshot | None = None,
        applied_planning_preferences: AppliedPlanningPreferences | None = None,
        applied_learned_preferences: AppliedLearnedPreferencesSnapshot | None = None,
        decision_context: DecisionContext | None = None,
        decision_trace: DecisionTrace | None = None,
        menu_plan_id: str | None = None,
        menu_plan_json: str | None = None,
    ) -> str:
        previous = await self._repository.get_active_for_user(user_id)
        strategy_id = await self._repository.save_active(
            user_id=user_id,
            strategy=strategy,
            plan_start_date=plan_start_date,
            reason_codes=reason_codes,
            applied_memory=applied_memory,
            applied_cooking_preference=applied_cooking_preference,
            applied_behavior=applied_behavior,
            applied_planning_preferences=applied_planning_preferences,
            applied_learned_preferences=applied_learned_preferences,
            decision_context=decision_context,
            decision_trace=decision_trace,
            menu_plan_id=menu_plan_id,
            menu_plan_json=menu_plan_json,
        )
        if previous is not None:
            try:
                superseded = await self._repository.get_by_id(previous.id, user_id)
                await self._ensure_outcomes_for_record(superseded)
            except Exception:
                # Retrospective metadata must never turn successful generation
                # into a failure or alter the new strategy.
                logger.warning(
                    "decision_outcomes_evaluation_failed strategy_id=%s",
                    previous.id,
                    exc_info=True,
                )
        return strategy_id

    def _build_applied_settings_payload(self, record: StrategyRecord, strategy: WeeklyStrategy):
        applied_cooking = self._repository.load_applied_cooking_preference(record)
        applied_behavior = self._repository.load_applied_behavior(record)
        applied_planning = self._repository.load_applied_planning_preferences(record)
        return build_applied_settings_response(
            strategy, applied_cooking, applied_behavior, applied_planning
        ).model_dump(mode="json")

    def _build_explanation_for_record(self, record: StrategyRecord, strategy: WeeklyStrategy) -> StrategyExplanation:
        recorded_codes = self._repository.load_reason_codes(record)
        if recorded_codes:
            return build_strategy_explanation(
                strategy,
                reason_codes=recorded_codes,
                source="recorded",
            )
        return build_strategy_explanation(strategy, source="inferred")

    def _build_decision_explanations_for_record(
        self,
        record: StrategyRecord,
        strategy: WeeklyStrategy,
        explanation: StrategyExplanation,
    ) -> DecisionExplanationCollection:
        trace = self._repository.load_decision_trace(record)
        if trace is not None:
            return build_decision_explanations(trace, strategy=strategy)
        return build_legacy_decision_explanations(explanation)

    async def _ensure_outcomes_for_record(
        self, record: StrategyRecord
    ) -> DecisionOutcomeSummary | None:
        existing = self._repository.load_decision_outcomes(record)
        if existing is not None:
            return build_outcome_summary(existing)
        if record.decision_outcomes_json is not None:
            # Malformed/unsupported write-once metadata stays unavailable.
            return None
        if record.status not in {
            StrategyStatus.COMPLETED.value,
            StrategyStatus.SUPERSEDED.value,
        }:
            return None
        trace = self._repository.load_decision_trace(record)
        if trace is None:
            return None
        strategy = self._repository.restore_weekly_strategy(record)
        events = await self._memory_repository.list_events_for_strategy(
            user_id=record.user_id,
            strategy_id=record.id,
        )
        collection = evaluate_decision_outcomes(
            trace,
            events,
            strategy=strategy,
        )
        saved = await self._repository.save_decision_outcomes_if_absent(
            strategy_id=record.id,
            user_id=record.user_id,
            outcomes=collection,
        )
        if not saved:
            refreshed = await self._repository.get_by_id(record.id, record.user_id)
            persisted = self._repository.load_decision_outcomes(refreshed)
            return build_outcome_summary(persisted) if persisted is not None else None
        return build_outcome_summary(collection)

    async def _outcomes_for_api(
        self, record: StrategyRecord
    ) -> DecisionOutcomeSummary | None:
        try:
            return await self._ensure_outcomes_for_record(record)
        except Exception:
            logger.warning(
                "decision_outcomes_evaluation_failed strategy_id=%s",
                record.id,
                exc_info=True,
            )
            return None

    async def get_current_strategy(
        self,
        user_id: int,
        current_date: date | None = None,
    ) -> dict[str, object]:
        """Returns API payload for current strategy or empty state."""
        today = current_date or date.today()
        record = await self._repository.get_active_for_user(user_id)

        if record is None:
            return {
                "status": "none",
                "strategy_id": None,
                "plan_start_date": None,
                "plan_end_date": None,
                "strategy": None,
                "explanation": None,
                "decision_explanations": None,
                "decision_outcomes": None,
                "applied_settings": None,
            }

        if is_strategy_completed(record, today):
            await self._repository.mark_completed(record.id, user_id)
            completed_record = await self._repository.get_by_id(record.id, user_id)
            await self._outcomes_for_api(completed_record)
            return {
                "status": "none",
                "strategy_id": None,
                "plan_start_date": None,
                "plan_end_date": None,
                "strategy": None,
                "explanation": None,
                "decision_explanations": None,
                "decision_outcomes": None,
                "applied_settings": None,
            }

        strategy = self._repository.restore_weekly_strategy(record)
        start = date.fromisoformat(record.plan_start_date)
        end = plan_end_date(start, record.plan_days)
        explanation = self._build_explanation_for_record(record, strategy)
        decision_explanations = self._build_decision_explanations_for_record(
            record, strategy, explanation
        )
        decision_outcomes = await self._outcomes_for_api(record)
        applied_settings = self._build_applied_settings_payload(record, strategy)

        return {
            "status": StrategyStatus.ACTIVE.value,
            "strategy_id": record.id,
            "plan_start_date": record.plan_start_date,
            "plan_end_date": end.isoformat(),
            "strategy": strategy.model_dump(mode="json"),
            "explanation": explanation.model_dump(mode="json"),
            "decision_explanations": decision_explanations.model_dump(mode="json"),
            "decision_outcomes": (
                decision_outcomes.model_dump(mode="json")
                if decision_outcomes is not None
                else None
            ),
            "applied_settings": applied_settings,
        }

    async def get_strategy_by_id(
        self,
        strategy_id: str,
        user_id: int,
    ) -> dict[str, object]:
        try:
            record = await self._repository.get_by_id(strategy_id, user_id)
        except StrategyNotFoundError as exc:
            raise StrategyNotFoundError(str(exc)) from exc

        strategy = self._repository.restore_weekly_strategy(record)
        start = date.fromisoformat(record.plan_start_date)
        end = plan_end_date(start, record.plan_days)
        explanation = self._build_explanation_for_record(record, strategy)
        decision_explanations = self._build_decision_explanations_for_record(
            record, strategy, explanation
        )
        decision_outcomes = await self._outcomes_for_api(record)
        applied_settings = self._build_applied_settings_payload(record, strategy)

        return {
            "strategy_id": record.id,
            "status": record.status,
            "plan_start_date": record.plan_start_date,
            "plan_end_date": end.isoformat(),
            "strategy": strategy.model_dump(mode="json"),
            "explanation": explanation.model_dump(mode="json"),
            "decision_explanations": decision_explanations.model_dump(mode="json"),
            "decision_outcomes": (
                decision_outcomes.model_dump(mode="json")
                if decision_outcomes is not None
                else None
            ),
            "applied_settings": applied_settings,
        }
