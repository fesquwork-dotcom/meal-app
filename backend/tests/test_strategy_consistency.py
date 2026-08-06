"""Sprint 10.11.6 — Strategy cook-day/leftovers consistency + preview feasibility."""

from __future__ import annotations

import asyncio
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

import config
from decision.engine import DecisionEngine
from decision.models import CookingDecision
from menu_generation.catalog_service import CatalogMenuGenerationService
from menu_generation.errors import CatalogGenerationError
from recipes.importer import RecipeCatalogImporter
from recipes.planning.context import build_planning_context_from_strategy
from recipes.planning.weights import WeeklyPlannerConfig
from strategy.behavior_context import StrategyBehaviorContext
from strategy.builder import StrategyBuilder
from strategy.feasibility import FeasibilityStatus, StrategyFeasibilityAnalyzer
from strategy.memory_context import StrategyMemoryContext
from strategy.models import WeeklyStrategy
from strategy.preview_service import (
    FEASIBILITY_WARNING_INFEASIBLE,
    FEASIBILITY_WARNING_RELAXATION,
    StrategyPreviewService,
)
from strategy.resolvers import resolve_cook_days, resolve_leftovers_enabled
from strategy.context import ProfileContext

CATALOG_ROOT = Path(__file__).resolve().parents[1] / "recipe_catalog"


@pytest.fixture
def catalog_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setattr(config, "ENVIRONMENT", "test")
    monkeypatch.setattr(config, "MEAL_GENERATION_ENGINE", "catalog_planner")
    monkeypatch.setenv("STRATEGY_PREVIEW_SECRET", "test-preview-secret-32chars!!")
    monkeypatch.setattr(
        config,
        "get_strategy_preview_secret",
        lambda: "test-preview-secret-32chars!!",
    )
    db = tmp_path / "sprint10116.db"

    async def _seed() -> None:
        report = await RecipeCatalogImporter(
            catalog_root=CATALOG_ROOT, db_path=db
        ).import_catalog(mode="replace_catalog")
        assert report.ok, report.to_dict()

    asyncio.run(_seed())
    return db


def _profile(goal: str, *, days: int = 5, cooktime: str = "medium") -> dict[str, object]:
    return {
        "goal": goal,
        "days": days,
        "budget": 4000.0,
        "cooktime": cooktime,
        "meal_types": ["breakfast", "lunch", "dinner"],
        "proteins": ["any"],
    }


def _build(goal: str, **kwargs) -> WeeklyStrategy:
    return StrategyBuilder(
        clock=lambda: datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    ).build(_profile(goal, **kwargs))


def _decision(goal: str, **kwargs):
    return DecisionEngine(
        clock=lambda: datetime(2026, 8, 6, 12, 0, tzinfo=timezone.utc)
    ).evaluate(_profile(goal, **kwargs))


def test_muscle_leftovers_false_daily_cook_days():
    strategy = _build("muscle", days=5, cooktime="medium")
    assert strategy.leftovers_enabled is False
    assert strategy.cook_days == [1, 2, 3, 4, 5]
    decision = _decision("muscle", days=5, cooktime="medium")
    cooking: CookingDecision = decision.decision.cooking
    assert cooking.leftovers_enabled is False
    assert cooking.cook_days == [1, 2, 3, 4, 5]
    assert cooking.batch_allowed is False


def test_muscle_seven_days_daily():
    strategy = _build("muscle", days=7, cooktime="medium")
    assert strategy.leftovers_enabled is False
    assert strategy.cook_days == [1, 2, 3, 4, 5, 6, 7]


def test_restaurant_unchanged_daily_no_leftovers():
    strategy = _build("restaurant", days=5, cooktime="medium")
    assert strategy.leftovers_enabled is False
    assert strategy.cook_days == [1, 2, 3, 4, 5]


def test_home_sparse_leftovers_preserved():
    strategy = _build("home", days=5, cooktime="medium")
    assert strategy.leftovers_enabled is True
    assert strategy.cook_days == [1, 3, 5]
    cooking = _decision("home", days=5).decision.cooking
    assert cooking.batch_allowed is True


def test_budget_sparse_leftovers_preserved():
    strategy = _build("budget", days=7, cooktime="medium")
    assert strategy.leftovers_enabled is True
    assert strategy.cook_days == [1, 3, 5, 7]


def test_healthy_weightloss_leftovers_true():
    healthy = _build("healthy", days=5, cooktime="medium")
    assert healthy.leftovers_enabled is True
    # healthy is not batch-eligible → daily when leftovers true
    assert healthy.cook_days == [1, 2, 3, 4, 5]
    wl = _build("weightloss", days=5, cooktime="medium")
    assert wl.leftovers_enabled is True


def test_fast_cooktime_daily_unchanged():
    strategy = _build("home", days=5, cooktime="fast")
    assert strategy.leftovers_enabled is True
    assert strategy.cook_days == [1, 2, 3, 4, 5]


def test_resolver_signature_uses_leftovers_flag():
    ctx = ProfileContext.from_profile(_profile("muscle"))
    leftovers = resolve_leftovers_enabled(ctx)
    assert leftovers is False
    assert resolve_cook_days(ctx, leftovers_enabled=False) == [1, 2, 3, 4, 5]
    # If leftovers were forced true, batch goal would still apply for muscle.
    assert resolve_cook_days(ctx, leftovers_enabled=True) == [1, 3, 5]


def test_decision_trace_muscle_no_leftovers_reason():
    result = _decision("muscle", days=5)
    assert "COOK_DAYS_DAILY_NO_LEFTOVERS" in result.reason_codes
    assert "COOK_DAYS_REDUCE_DAILY_WORK" not in result.reason_codes
    entry = next(
        e for e in result.trace.entries if e.decision_key == "cooking.cook_days"
    )
    assert entry.outcome.value == [1, 2, 3, 4, 5]
    applied = {r.rule_code: r.reason_code for r in entry.applied_rules}
    assert applied.get("COOK_DAYS_DAILY_NO_LEFTOVERS") == "COOK_DAYS_DAILY_NO_LEFTOVERS"
    rejected = {r.rule_code for r in entry.rejected_rules}
    assert "COOK_DAYS_BATCH_GOAL" in rejected


def test_muscle_production_feasible_and_generates(catalog_db: Path):
    async def _run() -> None:
        strategy = _build("muscle", days=5, cooktime="medium")
        feas = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy,
            build_planning_context_from_strategy(
                strategy, max_cooking_time_override=strategy.cooking_time_limit
            ),
        )
        assert feas.status == FeasibilityStatus.FEASIBLE
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=2,
            cooktime="medium",
        )
        assert result.get("meal_count") == 15
        relax = result.get("cook_day_relaxation") or {}
        assert relax.get("relaxation_used") is False
        assert strategy.cook_days == [1, 2, 3, 4, 5]

    asyncio.run(_run())


def test_home_control_sparse_feasible(catalog_db: Path):
    async def _run() -> None:
        strategy = _build("home", days=5, cooktime="medium")
        assert strategy.leftovers_enabled is True
        assert strategy.cook_days == [1, 3, 5]
        feas = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy,
            build_planning_context_from_strategy(
                strategy, max_cooking_time_override=strategy.cooking_time_limit
            ),
        )
        assert feas.status in {
            FeasibilityStatus.FEASIBLE,
            FeasibilityStatus.FEASIBLE_WITH_RELAXATION,
        }
        result = await CatalogMenuGenerationService(db_path=catalog_db).generate(
            strategy=strategy,
            persons=2,
            cooktime="medium",
        )
        assert result.get("meal_count") == 15
        assert int(result.get("leftover_count") or 0) >= 1

    asyncio.run(_run())


def test_preview_feasible_muscle(catalog_db: Path):
    async def _run() -> None:
        started = time.perf_counter()
        preview = await StrategyPreviewService(db_path=catalog_db).build_preview(
            _profile("muscle"),
            StrategyMemoryContext(),
            StrategyBehaviorContext.empty(),
            user_id=1,
            profile_revision=1,
            plan_start_date="2026-08-06",
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        assert preview.status == "ready"
        assert preview.feasibility_status == "FEASIBLE"
        assert preview.feasibility_warning is None
        assert preview.feasibility is not None
        assert preview.feasibility["status"] == "FEASIBLE"
        assert not any(
            w.code
            in {FEASIBILITY_WARNING_INFEASIBLE, FEASIBILITY_WARNING_RELAXATION}
            for w in preview.warnings
        )
        assert preview.strategy is not None
        assert preview.strategy.cook_days == [1, 2, 3, 4, 5]
        assert preview.preview_token
        # Smoke latency budget (structural analyzer, not CI hard fail above 5s)
        assert elapsed_ms < 5000

    asyncio.run(_run())


def test_preview_infeasible_synthetic(catalog_db: Path):
    async def _run() -> None:
        # Force infeasible: leftovers off + sparse cook days (bypasses builder consistency).
        strategy = WeeklyStrategy(
            strategy_version=5,
            goal="muscle",  # type: ignore[arg-type]
            days=5,
            budget=4000.0,
            meal_types=["breakfast", "lunch", "dinner"],  # type: ignore[arg-type]
            meals_per_day=3,
            cook_days=[1, 3, 5],
            shopping_days=[1],
            leftovers_enabled=False,
            repeat_breakfasts=False,
            repeat_lunches=True,
            repeat_dinners=False,
            preferred_proteins=["any"],  # type: ignore[arg-type]
            excluded_products=[],
            cooking_time_limit=45,
            prefer_faster_meals=False,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        feas = await StrategyFeasibilityAnalyzer(db_path=catalog_db).analyze(
            strategy,
            build_planning_context_from_strategy(strategy, max_cooking_time_override=45),
        )
        assert feas.status == FeasibilityStatus.INFEASIBLE

        # Preview path uses builder (muscle now daily). Inject analyzer result via
        # synthetic WeeklyStrategy through a custom analyzer stub is heavy —
        # instead call preview service helper by monkeypatching analyze.
        service = StrategyPreviewService(db_path=catalog_db)

        async def _fake_analyze(s, context):
            return feas

        service._analyzer = lambda: type(
            "A",
            (),
            {"analyze": staticmethod(_fake_analyze)},
        )()

        # Still need builder to return sparse+no leftovers — override builder.
        class _FakeBuilder:
            def build_with_reasons_from_inputs(self, *args, **kwargs):
                from strategy.build_result import StrategyBuildResult

                return StrategyBuildResult(
                    strategy=strategy,
                    reason_codes=["GOAL_MUSCLE", "COOK_DAYS_DAILY_NO_LEFTOVERS"],
                    applied_memory=None,
                    applied_cooking_preference=None,
                    applied_behavior=None,
                    applied_planning_preferences=None,
                    decision_trace=None,
                )

        service._builder = _FakeBuilder()  # type: ignore[assignment]
        preview = await service.build_preview(
            _profile("muscle"),
            StrategyMemoryContext(),
            StrategyBehaviorContext.empty(),
            user_id=1,
            profile_revision=1,
            plan_start_date="2026-08-06",
        )
        assert preview.status == "ready"
        assert preview.feasibility_status == "INFEASIBLE"
        assert preview.feasibility_warning
        assert any(w.code == FEASIBILITY_WARNING_INFEASIBLE for w in preview.warnings)
        assert len(preview.warnings) > 0
        assert preview.preview_token

    asyncio.run(_run())


def test_generation_still_rechecks_infeasible(catalog_db: Path):
    async def _run() -> None:
        strategy = WeeklyStrategy(
            strategy_version=5,
            goal="muscle",  # type: ignore[arg-type]
            days=5,
            budget=4000.0,
            meal_types=["breakfast", "lunch", "dinner"],  # type: ignore[arg-type]
            meals_per_day=3,
            cook_days=[1, 3, 5],
            shopping_days=[1],
            leftovers_enabled=False,
            repeat_breakfasts=False,
            repeat_lunches=False,
            repeat_dinners=False,
            preferred_proteins=["any"],  # type: ignore[arg-type]
            excluded_products=[],
            cooking_time_limit=45,
            prefer_faster_meals=False,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )
        with pytest.raises(CatalogGenerationError) as exc:
            await CatalogMenuGenerationService(db_path=catalog_db).generate(
                strategy=strategy,
                persons=2,
                cooktime="medium",
            )
        assert exc.value.code == CatalogGenerationError.STRATEGY_INFEASIBLE

    asyncio.run(_run())


def test_planner_limits_unchanged():
    cfg = WeeklyPlannerConfig()
    assert cfg.max_leftovers_per_cook == 1
    assert cfg.max_extra_cook_days == 1
    assert cfg.beam_width == 8
    assert cfg.candidate_pool_size == 15
    assert cfg.max_states == 4000


def test_catalog_still_86(catalog_db: Path):
    async def _run() -> None:
        from recipes.repository import RecipeRepository

        assert await RecipeRepository(catalog_db).count_recipes() == 86

    asyncio.run(_run())
