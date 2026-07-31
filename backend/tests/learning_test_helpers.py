"""Shared setup for Decision Learning API tests."""

import asyncio
from dataclasses import replace
from datetime import date

from decision.engine import DecisionEngine
from decision.outcome import evaluate_decision_outcomes
from memory.repository import MemoryRepository
from strategy.repository import StrategyRepository
from test_decision_outcomes import _event
from profile_test_helpers import save_profile


def seed_learning_candidate(client, *, user_id: int = 42) -> tuple[str, int]:
    profile_response = save_profile(
        client,
        planning_preferences={"prefer_familiar_meals": False},
        cooking_preferences={"prefer_faster_meals": False},
    )
    assert profile_response.status_code == 200, profile_response.text
    revision = profile_response.json()["revision"]

    evaluation = DecisionEngine().evaluate(
        {
            "days": 7,
            "planning_preferences": {"prefer_familiar_meals": False},
            "cooking_preferences": {"prefer_faster_meals": False},
        }
    )
    repository = StrategyRepository()
    strategy_id = asyncio.run(
        repository.save_active(
            user_id=user_id,
            strategy=evaluation.strategy,
            plan_start_date=date(2026, 7, 1),
            reason_codes=evaluation.reason_codes,
            decision_context=evaluation.decision,
            decision_trace=evaluation.trace,
        )
    )
    events = [
        replace(_event(index), user_id=user_id, strategy_id=strategy_id)
        for index in range(9)
    ]
    memory = MemoryRepository()
    for event in events:
        asyncio.run(memory.insert_event(event))
    outcomes = evaluate_decision_outcomes(
        evaluation.trace, events, strategy=evaluation.strategy
    )
    asyncio.run(repository.mark_completed(strategy_id, user_id))
    assert asyncio.run(
        repository.save_decision_outcomes_if_absent(
            strategy_id=strategy_id,
            user_id=user_id,
            outcomes=outcomes,
        )
    )
    return strategy_id, revision
