"""Sprint 9.5 — deterministic QA fixture loader for local dev tools.

Builds small, self-consistent per-scenario data snapshots pinned to the QA
anchor clock (``dev_tools.clock``) so a given scenario always looks the same
regardless of when it is loaded. Gated by ``assert_dev_tools_enabled`` — never
reachable in production.

This module intentionally duplicates the profile/menu builders from
``tests/strategy_fixtures.py`` and ``tests/menu_fixtures.py`` instead of
importing them: dev tooling must not depend on the test package.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

import aiosqlite

import database
from decision.outcome import DecisionFeedback, DecisionOutcome, DecisionOutcomeCollection
from dev_tools.clock import QA_ANCHOR_DATE, qa_plan_date
from dev_tools.guards import assert_dev_tools_enabled
from dev_tools.reset import DevResetService
from dev_tools.scenarios import QA_SCENARIO_NAMES
from learned_preferences.repository import LearnedPreferenceRepository, preference_key
from memory.constants import MemoryEventType
from strategy.applied_learned_preferences import (
    AppliedLearnedPreferenceDecision,
    AppliedLearnedPreferencesSnapshot,
)
from strategy.builder import StrategyBuilder
from strategy.repository import StrategyRepository


def _ensure_no_claude_imports() -> None:
    """Never invoked — documents that this module has no Claude/Anthropic import.

    QA fixtures must stay deterministic, offline, and free of LLM calls.
    Keep it that way: do not import ``claude_service`` or ``anthropic`` here.
    """
    return None


_FAMILIAR_TYPE = "prefer_familiar_meals"
_FAMILIAR_DECISION_KEY = "planning.prefer_familiar_meals"
_FAMILIAR_LP_ID = preference_key(_FAMILIAR_TYPE)
_LP_SOURCE = "decision_learning"


def build_test_profile(**overrides: object) -> dict:
    """Minimal valid profile dict (mirrors tests/strategy_fixtures.py)."""
    profile: dict[str, object] = {
        "goal": "home",
        "days": 3,
        "budget": 3000.0,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "meals_per_day": 3,
        "proteins": ["any"],
        "cooktime": "medium",
        "allergies": "нет",
        "store": "any",
    }
    profile.update(overrides)
    return profile


def build_test_menu(*, days: int = 3, budget: float = 3000.0) -> dict:
    """Minimal valid menu dict (trimmed copy of tests/menu_fixtures.py shape)."""
    meal_types = ("breakfast", "lunch", "dinner")
    meal_names = {
        "breakfast": "Овсянка",
        "lunch": "Гречка с курицей",
        "dinner": "Куриная грудка с рисом",
    }
    price_per_meal = round(budget / (days * len(meal_types)), 2)

    days_plan: list[dict[str, object]] = []
    for day_index in range(days):
        day_num = day_index + 1
        meals: list[dict[str, object]] = []
        for meal_type in meal_types:
            meal_id = f"day{day_num}_{meal_type}"
            meals.append(
                {
                    "type": meal_type,
                    "recipe_name": meal_names[meal_type],
                    "meal_id": meal_id,
                    "recipe_id": f"recipe_{meal_type}",
                    "requires_cooking": True,
                    "prepared_on_day": day_num,
                    "uses_leftovers": False,
                    "source_meal_id": None,
                    "cooking_instance_id": f"cook_{meal_id}",
                }
            )
        days_plan.append({"day": f"День {day_num}", "meals": meals})

    recipes = [
        {
            "name": name,
            "recipe_id": f"recipe_{meal_type}",
            "emoji": "🍲",
            "cook_time": "30 мин",
            "kbju": "Б:20г Ж:10г У:30г",
            "ingredients": [
                {"name": "Основной продукт", "amount": "300 г", "contribution": "purchase"},
                {"name": "Соль", "amount": "по вкусу", "contribution": "pantry"},
            ],
            "steps": ["Подготовить ингредиенты", "Приготовить блюдо"],
        }
        for meal_type, name in meal_names.items()
    ]
    basket_items = [
        {"name": "Основной продукт", "weight": "300 г", "price": price_per_meal}
        for _ in meal_names
    ]

    return {
        "summary": "Сбалансированное меню на несколько дней (QA fixture).",
        "total_cost": round(price_per_meal * len(meal_names), 2),
        "days_plan": days_plan,
        "recipes": recipes,
        "basket": [{"category": "Продукты", "items": basket_items}],
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _menu_plan_json(*, days: int = 3, budget: float = 3000.0) -> str:
    return json.dumps(build_test_menu(days=days, budget=budget), ensure_ascii=False)


def _applied_learned_snapshot(*, applied: bool = True) -> AppliedLearnedPreferencesSnapshot:
    return AppliedLearnedPreferencesSnapshot(
        enabled=True,
        decisions=[
            AppliedLearnedPreferenceDecision(
                preference_type=_FAMILIAR_TYPE,
                applied=applied,
                reason_code="LEARNED_FAMILIAR_MEALS_APPLIED",
                decision_key=_FAMILIAR_DECISION_KEY,
            )
        ],
    )


def _decision_outcomes_json(
    *, status: str, result: str, confidence: str, evidence_count: int
) -> str:
    outcome = DecisionOutcome(
        decision_key=_FAMILIAR_DECISION_KEY,
        result=result,
        confidence=confidence,
        evidence_count=evidence_count,
        status=status,
    )
    feedback = DecisionFeedback(
        decision_key=_FAMILIAR_DECISION_KEY,
        feedback="QA fixture retrospective feedback.",
        recommendation="QA fixture recommendation.",
        confidence=confidence,
    )
    return DecisionOutcomeCollection(outcomes=[outcome], feedback=[feedback]).to_json()


class QaFixtureService:
    """Loads deterministic per-scenario datasets for local QA (Sprint 9.5)."""

    def __init__(self) -> None:
        self._strategies = StrategyRepository()
        self._reset = DevResetService()
        self._learned = LearnedPreferenceRepository()

    async def load_scenario(self, user_id: int, scenario: str) -> dict:
        assert_dev_tools_enabled()
        if scenario not in QA_SCENARIO_NAMES:
            raise ValueError(f"Unknown QA scenario: {scenario}")

        if scenario == "fresh_user":
            await self._reset.reset_current_user(user_id, mode="full_user")
            return self._result(scenario)

        await self._reset.reset_current_user(user_id, mode="history_only")
        await self._seed_profile(user_id)

        handler = getattr(self, f"_load_{scenario}")
        await handler(user_id)
        return self._result(scenario)

    def _result(self, scenario: str) -> dict:
        return {
            "scenario": scenario,
            "status": "ok",
            "anchor_date": QA_ANCHOR_DATE.isoformat(),
        }

    async def _seed_profile(self, user_id: int) -> None:
        await database.save_profile(user_id, build_test_profile())

    # ---- per-scenario builders ---------------------------------------------

    async def _load_profile_ready(self, user_id: int) -> None:
        del user_id  # Profile already seeded by load_scenario; nothing else needed.

    async def _load_active_week(self, user_id: int) -> None:
        await self._save_strategy(
            user_id,
            weeks_before_anchor=0,
            menu_plan_id=str(uuid.uuid4()),
            menu_plan_json=_menu_plan_json(),
        )

    async def _load_completed_history(self, user_id: int) -> None:
        for weeks_before in (3, 2, 1):
            strategy_id = await self._save_strategy(user_id, weeks_before_anchor=weeks_before)
            await self._mark_completed(strategy_id)

    async def _load_learning_candidate(self, user_id: int) -> None:
        await self._seed_accepted_recommendation(user_id)

    async def _load_learned_preference_active(self, user_id: int) -> None:
        await self._ensure_active_learned_preference(user_id)
        await self._save_strategy(
            user_id,
            weeks_before_anchor=0,
            applied_learned=_applied_learned_snapshot(),
        )

    async def _load_learned_preference_insufficient(self, user_id: int) -> None:
        await self._ensure_active_learned_preference(user_id)
        await self._seed_applied_plan(user_id, weeks_before_anchor=1)

    async def _load_learned_preference_emerging(self, user_id: int) -> None:
        await self._ensure_active_learned_preference(user_id)
        for weeks_before in (3, 2, 1):
            await self._seed_applied_plan(
                user_id, weeks_before_anchor=weeks_before, positive=True
            )

    async def _load_learned_preference_effective(self, user_id: int) -> None:
        await self._ensure_active_learned_preference(user_id)
        for weeks_before in (4, 3, 2, 1):
            await self._seed_applied_plan(
                user_id, weeks_before_anchor=weeks_before, positive=True
            )

    async def _load_learned_preference_ineffective(self, user_id: int) -> None:
        await self._ensure_active_learned_preference(user_id)
        for weeks_before in (4, 3, 2, 1):
            await self._seed_applied_plan(
                user_id, weeks_before_anchor=weeks_before, high_replacement=True
            )

    async def _load_review_dismissed(self, user_id: int) -> None:
        await self._load_learned_preference_ineffective(user_id)
        await self._learned.set_last_review_generation(
            user_id=user_id, preference_id=_FAMILIAR_LP_ID, generation=1
        )

    async def _load_review_new_generation(self, user_id: int) -> None:
        await self._ensure_active_learned_preference(user_id)
        for weeks_before in range(8, 0, -1):
            await self._seed_applied_plan(
                user_id, weeks_before_anchor=weeks_before, high_replacement=True
            )
        # Cohort 1 was already dismissed; 8 plans now form cohort 2 (8 // 4),
        # so the review must resurface.
        await self._learned.set_last_review_generation(
            user_id=user_id, preference_id=_FAMILIAR_LP_ID, generation=1
        )

    async def _load_legacy_partial_data(self, user_id: int) -> None:
        strategy_id = await self._save_strategy(
            user_id, weeks_before_anchor=1, applied_learned=None
        )
        await self._mark_completed(strategy_id)

    # ---- shared helpers -----------------------------------------------------

    async def _save_strategy(
        self,
        user_id: int,
        *,
        weeks_before_anchor: int,
        applied_learned: AppliedLearnedPreferencesSnapshot | None = None,
        menu_plan_id: str | None = None,
        menu_plan_json: str | None = None,
    ) -> str:
        strategy = StrategyBuilder().build(build_test_profile())
        return await self._strategies.save_active(
            user_id=user_id,
            strategy=strategy,
            plan_start_date=qa_plan_date(weeks_before_anchor=weeks_before_anchor),
            applied_learned_preferences=applied_learned,
            menu_plan_id=menu_plan_id,
            menu_plan_json=menu_plan_json,
        )

    async def _seed_applied_plan(
        self,
        user_id: int,
        *,
        weeks_before_anchor: int,
        positive: bool = False,
        high_replacement: bool = False,
    ) -> str:
        """One completed strategy with the Learned Preference marked applied."""
        strategy_id = await self._save_strategy(
            user_id,
            weeks_before_anchor=weeks_before_anchor,
            applied_learned=_applied_learned_snapshot(),
        )
        await self._mark_completed(strategy_id)

        if positive:
            await self._insert_memory_events(
                user_id,
                strategy_id,
                event_type=MemoryEventType.MEAL_SUITED.value,
                count=2,
            )
            await self._set_decision_outcomes(
                strategy_id,
                _decision_outcomes_json(
                    status="successful",
                    result="meals_suited_confirmed",
                    confidence="strong",
                    evidence_count=2,
                ),
            )
        elif high_replacement:
            await self._insert_memory_events(
                user_id,
                strategy_id,
                event_type=MemoryEventType.MEAL_REPLACED.value,
                count=5,
            )
            await self._set_decision_outcomes(
                strategy_id,
                _decision_outcomes_json(
                    status="unsuccessful",
                    result="high_replacement_rate",
                    confidence="strong",
                    evidence_count=5,
                ),
            )
        return strategy_id

    async def _ensure_active_learned_preference(self, user_id: int) -> None:
        existing = await self._learned.get(user_id, _FAMILIAR_LP_ID)
        if existing is not None:
            return
        await self._learned.create(
            user_id=user_id,
            preference_id=_FAMILIAR_LP_ID,
            preference_type=_FAMILIAR_TYPE,
            source=_LP_SOURCE,
            evidence_json=json.dumps(
                {"source": _LP_SOURCE, "confidence": "strong"}, ensure_ascii=False
            ),
            preference_json=json.dumps({"type": _FAMILIAR_TYPE}, ensure_ascii=False),
            status="active",
        )

    async def _seed_accepted_recommendation(self, user_id: int) -> None:
        """Mirrors the seed pattern in tests/test_learned_preference_api.py."""
        db_path = database.resolve_database_path()
        now = _utc_now_iso()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_learning_recommendations_table(db)
            await db.execute(
                """
                INSERT INTO learning_recommendations (
                    id, user_id, recommendation_key, recommendation_type,
                    decision_key, status, confidence, rule_version,
                    source_strategy_id, profile_patch_json,
                    created_at, updated_at, accepted_at, dismissed_at, expired_at
                ) VALUES (?, ?, ?, ?, ?, 'accepted', 'strong', 1, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    str(uuid.uuid4()),
                    user_id,
                    f"v1:profile_enable_{_FAMILIAR_TYPE}",
                    f"profile_enable_{_FAMILIAR_TYPE}",
                    _FAMILIAR_DECISION_KEY,
                    "qa-fixture-strategy",
                    json.dumps(
                        {"planning_preferences": {_FAMILIAR_TYPE: True}}, ensure_ascii=False
                    ),
                    now,
                    now,
                    now,
                ),
            )
            await db.commit()

    async def _mark_completed(self, strategy_id: str) -> None:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await db.execute(
                """
                UPDATE weekly_strategies
                SET status = 'completed', completed_at = updated_at
                WHERE id = ?
                """,
                (strategy_id,),
            )
            await db.commit()

    async def _set_decision_outcomes(self, strategy_id: str, outcomes_json: str) -> None:
        db_path = database.resolve_database_path()
        async with aiosqlite.connect(db_path) as db:
            await database._ensure_decision_outcomes_column(db)
            await db.execute(
                "UPDATE weekly_strategies SET decision_outcomes_json = ? WHERE id = ?",
                (outcomes_json, strategy_id),
            )
            await db.commit()

    async def _insert_memory_events(
        self,
        user_id: int,
        strategy_id: str,
        *,
        event_type: str,
        count: int,
    ) -> None:
        db_path = database.resolve_database_path()
        now = _utc_now_iso()
        async with aiosqlite.connect(db_path) as db:
            for index in range(count):
                event_id = str(uuid.uuid4())
                meal_id = f"{strategy_id}-{event_type}-{index}"
                await db.execute(
                    """
                    INSERT OR IGNORE INTO memory_events (
                        id, user_id, event_type, event_key, strategy_id, meal_id,
                        recipe_id, reason_code, target_type, target_value, target_label,
                        metadata_json, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, NULL, ?)
                    """,
                    (event_id, user_id, event_type, event_id, strategy_id, meal_id, now),
                )
            await db.commit()
