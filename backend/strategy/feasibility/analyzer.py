"""Deterministic Strategy Feasibility Analyzer (Sprint 10.11.4).

Structural check between StrategyBuilder and WeeklyRecipePlanner.
Does not run beam search and does not mutate WeeklyStrategy.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from recipes.enums import MealType, RecipeStatus
from recipes.models import Recipe
from recipes.planning.constraints import has_excluded_ingredient, has_excluded_protein
from recipes.planning.context import WeeklyPlanningContext
from recipes.planning.slots import make_slot_id
from recipes.planning.weights import WeeklyPlannerConfig
from recipes.repository import RecipeRepository
from strategy.feasibility.models import (
    CandidateCoverage,
    CatalogGapSignal,
    FeasibilityIssue,
    FeasibilityIssueCode,
    FeasibilityStatus,
    SlotRequirement,
    StrategyFeasibilityResult,
    SuggestedAdjustment,
    SuggestionCode,
)
from strategy.models import WeeklyStrategy

logger = logging.getLogger(__name__)

# Meal types that typically need leftover/batch coverage on non-cook days.
_COVERAGE_MEAL_TYPES = frozenset({MealType.LUNCH, MealType.DINNER})


def _meal_type_ok(recipe: Recipe, meal_type: MealType) -> bool:
    if recipe.primary_meal_type == meal_type:
        return True
    return any(link.meal_type == meal_type for link in recipe.meal_types)


def _passes_profile(
    recipe: Recipe,
    context: WeeklyPlanningContext,
) -> bool:
    if recipe.id in context.avoided_recipe_ids:
        return False
    if has_excluded_ingredient(recipe, context.excluded_ingredient_ids):
        return False
    if has_excluded_protein(recipe, context.excluded_protein_sources):
        return False
    if context.allowed_budget_classes is not None:
        allowed = {b.value for b in context.allowed_budget_classes}
        if recipe.budget_class.value not in allowed:
            return False
    return True


def _passes_time(recipe: Recipe, max_time: int | None) -> bool:
    if max_time is None:
        return True
    return int(recipe.total_time_minutes) <= int(max_time)


class StrategyFeasibilityAnalyzer:
    """Structural feasibility of WeeklyStrategy against the recipe catalog."""

    def __init__(
        self,
        *,
        repository: RecipeRepository | None = None,
        db_path: Path | str | None = None,
        max_extra_cook_days: int | None = None,
    ) -> None:
        self._repository = repository or RecipeRepository(db_path)
        self._max_extra_cook_days = (
            max_extra_cook_days
            if max_extra_cook_days is not None
            else WeeklyPlannerConfig().max_extra_cook_days
        )

    async def analyze(
        self,
        strategy: WeeklyStrategy,
        context: WeeklyPlanningContext,
    ) -> StrategyFeasibilityResult:
        recipes_by_meal: dict[MealType, list[Recipe]] = {}
        for mt in context.meal_types:
            thin = await self._repository.list_by_meal_type(mt)
            full: list[Recipe] = []
            for recipe in thin:
                loaded = await self._repository.get_recipe_with_dependencies(recipe.id)
                if loaded is not None and loaded.status == RecipeStatus.ACTIVE:
                    full.append(loaded)
            recipes_by_meal[mt] = full

        return self.analyze_with_recipes(strategy, context, recipes_by_meal)

    def analyze_with_recipes(
        self,
        strategy: WeeklyStrategy,
        context: WeeklyPlanningContext,
        recipes_by_meal: dict[MealType, list[Recipe]],
    ) -> StrategyFeasibilityResult:
        """Pure deterministic analysis given preloaded meal-type recipe lists."""
        cook_days = sorted(set(strategy.cook_days) or set(range(1, strategy.days + 1)))
        preferred = set(cook_days)
        non_cook_days = [
            d for d in range(1, strategy.days + 1) if d not in preferred
        ]
        max_time = context.max_cooking_time
        leftovers = bool(context.leftovers_enabled)

        coverage_rows: list[CandidateCoverage] = []
        slot_requirements: list[SlotRequirement] = []
        issues: list[FeasibilityIssue] = []
        catalog_gaps: list[CatalogGapSignal] = []
        suggestions: list[SuggestedAdjustment] = []
        cook_day_gaps: list[str] = []

        # Precompute per meal_type candidate stats (profile + time + batch/lo).
        stats_by_meal = self._meal_stats(recipes_by_meal, context, max_time)
        for mt, stats in stats_by_meal.items():
            coverage_rows.append(
                CandidateCoverage(
                    meal_type=mt.value,
                    total_meal_type=stats["total"],
                    after_profile_filters=stats["after_profile"],
                    after_time_limit=stats["after_time"],
                    batch_leftover_before_time=stats["batch_lo_before_time"],
                    batch_leftover_after_time=stats["batch_lo_after_time"],
                    nocook_after_time=stats["nocook_after_time"],
                    min_batch_leftover_time=stats["min_batch_lo_time"],
                )
            )

        uncovered_needing_extra: list[SlotRequirement] = []

        for day in non_cook_days:
            source_day = self._preceding_cook_day(day, preferred)
            for meal_type in context.meal_types:
                if meal_type not in _COVERAGE_MEAL_TYPES:
                    # Breakfast / snack: no-cook or soft cook-day miss; not structural
                    # leftover-chain requirements for v1.
                    req = SlotRequirement(
                        slot_id=make_slot_id(day, meal_type),
                        day_index=day,
                        meal_type=meal_type.value,
                        is_cook_day=False,
                        coverage_modes=["nocook", "extra_cook"],
                        source_cook_day=source_day,
                        covered=True,
                        covered_by="soft_meal_type",
                    )
                    slot_requirements.append(req)
                    continue

                slot_id = make_slot_id(day, meal_type)
                modes: list[str] = []
                covered = False
                covered_by: str | None = None
                stats = stats_by_meal.get(meal_type, {})

                batch_after = int(stats.get("batch_lo_after_time", 0))
                batch_before = int(stats.get("batch_lo_before_time", 0))
                nocook = int(stats.get("nocook_after_time", 0))

                if leftovers and source_day is not None and batch_after > 0:
                    modes.append("leftover_from_preceding_cook")
                    covered = True
                    covered_by = "batch_leftover"
                elif nocook > 0:
                    modes.append("nocook")
                    covered = True
                    covered_by = "nocook"
                else:
                    modes.append("extra_cook_required")
                    if leftovers and source_day is not None and batch_before > 0 and batch_after == 0:
                        issues.append(
                            FeasibilityIssue(
                                code=FeasibilityIssueCode.TIME_LIMIT_REMOVES_REQUIRED_BATCH_CANDIDATES.value,
                                target_slot=slot_id,
                                source_cook_day=source_day,
                                meal_type=meal_type.value,
                                time_limit=max_time,
                                candidate_count=0,
                                message=(
                                    f"Batch+leftover {meal_type.value} candidates exist "
                                    f"before time filter ({batch_before}) but none after "
                                    f"CTL={max_time}"
                                ),
                                details={
                                    "batch_leftover_before_time": batch_before,
                                    "batch_leftover_after_time": 0,
                                    "after_profile": stats.get("after_profile", 0),
                                },
                            )
                        )
                        catalog_gaps.append(
                            CatalogGapSignal(
                                meal_type=meal_type.value,
                                required_properties=[
                                    "batch_friendly",
                                    "leftover_friendly",
                                ],
                                max_time=max_time,
                                needed_for="non_cook_day",
                                source_cook_day=source_day,
                                target_slot=slot_id,
                            )
                        )
                        min_t = stats.get("min_batch_lo_time")
                        if min_t is not None and max_time is not None:
                            suggestions.append(
                                SuggestedAdjustment(
                                    suggestion=SuggestionCode.RELAX_TIME_LIMIT.value,
                                    reason=(
                                        f"No {meal_type.value} batch candidate "
                                        f"<= {max_time} minutes on cook day {source_day}"
                                    ),
                                    current=int(max_time),
                                    minimum_supported=int(min_t),
                                    details={"target_slot": slot_id},
                                )
                            )
                    elif leftovers and source_day is not None and batch_before == 0:
                        issues.append(
                            FeasibilityIssue(
                                code=FeasibilityIssueCode.NO_BATCH_LEFTOVER_CANDIDATE.value,
                                target_slot=slot_id,
                                source_cook_day=source_day,
                                meal_type=meal_type.value,
                                time_limit=max_time,
                                candidate_count=0,
                                message=(
                                    f"No batch+leftover {meal_type.value} candidates "
                                    f"for preceding cook day {source_day}"
                                ),
                            )
                        )
                        catalog_gaps.append(
                            CatalogGapSignal(
                                meal_type=meal_type.value,
                                required_properties=[
                                    "batch_friendly",
                                    "leftover_friendly",
                                ],
                                max_time=max_time,
                                needed_for="non_cook_day",
                                source_cook_day=source_day,
                                target_slot=slot_id,
                            )
                        )
                        suggestions.append(
                            SuggestedAdjustment(
                                suggestion=SuggestionCode.CATALOG_COVERAGE_REQUIRED.value,
                                reason=(
                                    f"Catalog lacks batch+leftover {meal_type.value} "
                                    f"recipes compatible with current profile"
                                ),
                                details={"target_slot": slot_id},
                            )
                        )
                    else:
                        issues.append(
                            FeasibilityIssue(
                                code=FeasibilityIssueCode.NON_COOK_DAY_UNCOVERED.value,
                                target_slot=slot_id,
                                source_cook_day=source_day,
                                meal_type=meal_type.value,
                                time_limit=max_time,
                                candidate_count=0,
                                message=f"Non-cook slot {slot_id} has no leftover/nocook path",
                            )
                        )

                    if nocook == 0:
                        issues.append(
                            FeasibilityIssue(
                                code=FeasibilityIssueCode.NO_NOCOOK_ALTERNATIVE.value,
                                target_slot=slot_id,
                                meal_type=meal_type.value,
                                time_limit=max_time,
                                candidate_count=0,
                                message=f"No no-cook {meal_type.value} alternative under CTL",
                            )
                        )

                    suggestions.append(
                        SuggestedAdjustment(
                            suggestion=SuggestionCode.ADD_COOK_DAY.value,
                            day=day,
                            reason=(
                                f"No {meal_type.value} batch candidate covers "
                                f"non-cook day {day}"
                            ),
                            details={"target_slot": slot_id},
                        )
                    )
                    cook_day_gaps.append(slot_id)

                req = SlotRequirement(
                    slot_id=slot_id,
                    day_index=day,
                    meal_type=meal_type.value,
                    is_cook_day=False,
                    coverage_modes=modes,
                    source_cook_day=source_day,
                    covered=covered,
                    covered_by=covered_by,
                )
                slot_requirements.append(req)
                if not covered:
                    uncovered_needing_extra.append(req)

                # Per-source-day coverage row for diagnostics.
                if source_day is not None:
                    coverage_rows.append(
                        CandidateCoverage(
                            meal_type=meal_type.value,
                            cook_day=source_day,
                            total_meal_type=int(stats.get("total", 0)),
                            after_profile_filters=int(stats.get("after_profile", 0)),
                            after_time_limit=int(stats.get("after_time", 0)),
                            batch_leftover_before_time=batch_before,
                            batch_leftover_after_time=batch_after,
                            nocook_after_time=nocook,
                            min_batch_leftover_time=stats.get("min_batch_lo_time"),
                        )
                    )

        # Unique suggestions by (suggestion, day, current)
        suggestions = self._dedupe_suggestions(suggestions)
        # Deduplicate issues by code+target_slot
        issues = self._dedupe_issues(issues)

        gap_count = len(uncovered_needing_extra)
        max_extra = int(self._max_extra_cook_days)

        if gap_count == 0:
            status = FeasibilityStatus.FEASIBLE
        elif gap_count <= max_extra:
            status = FeasibilityStatus.FEASIBLE_WITH_RELAXATION
            suggestions.append(
                SuggestedAdjustment(
                    suggestion=SuggestionCode.ALLOW_EXTRA_COOK_DAY.value,
                    reason=(
                        f"{gap_count} non-cook lunch/dinner slot(s) need an extra "
                        f"cook day; max_extra_cook_days={max_extra}"
                    ),
                    details={"gap_slots": [s.slot_id for s in uncovered_needing_extra]},
                )
            )
            suggestions = self._dedupe_suggestions(suggestions)
        else:
            status = FeasibilityStatus.INFEASIBLE
            issues.append(
                FeasibilityIssue(
                    code=FeasibilityIssueCode.EXTRA_COOK_DAYS_INSUFFICIENT.value,
                    message=(
                        f"{gap_count} uncovered non-cook lunch/dinner slots exceed "
                        f"max_extra_cook_days={max_extra}"
                    ),
                    details={
                        "gap_slots": [s.slot_id for s in uncovered_needing_extra],
                        "max_extra_cook_days": max_extra,
                    },
                )
            )
            issues = self._dedupe_issues(issues)

        warning_ru = self._warning_ru(
            status=status,
            strategy=strategy,
            max_time=max_time,
            issues=issues,
            non_cook_days=non_cook_days,
        )

        result = StrategyFeasibilityResult(
            status=status,
            feasible=status != FeasibilityStatus.INFEASIBLE,
            issues=issues,
            slot_requirements=slot_requirements,
            candidate_coverage=coverage_rows,
            cook_day_gaps=sorted(set(cook_day_gaps)),
            suggested_adjustments=suggestions,
            catalog_gaps=catalog_gaps,
            diagnostics={
                "cook_days": cook_days,
                "non_cook_days": non_cook_days,
                "time_limit": max_time,
                "leftovers_enabled": leftovers,
                "max_extra_cook_days": max_extra,
                "uncovered_lunch_dinner_slots": [
                    s.slot_id for s in uncovered_needing_extra
                ],
                "issue_count": len(issues),
                "gap_kind": (
                    "catalog_strategy"
                    if status == FeasibilityStatus.INFEASIBLE
                    else "none"
                ),
            },
            warning_ru=warning_ru,
        )

        logger.info(
            "strategy_feasibility_checked status=%s cook_days=%s time_limit=%s "
            "issue_count=%s leftovers=%s",
            result.status.value,
            cook_days,
            max_time,
            len(result.issues),
            leftovers,
        )
        if result.status == FeasibilityStatus.INFEASIBLE:
            logger.warning(
                "strategy_infeasible issue_codes=%s affected_slots=%s "
                "suggested_adjustments=%s",
                [i.code for i in result.issues],
                result.cook_day_gaps,
                [a.suggestion for a in result.suggested_adjustments],
            )
        return result

    def _meal_stats(
        self,
        recipes_by_meal: dict[MealType, list[Recipe]],
        context: WeeklyPlanningContext,
        max_time: int | None,
    ) -> dict[MealType, dict[str, Any]]:
        out: dict[MealType, dict[str, Any]] = {}
        for mt, recipes in recipes_by_meal.items():
            # Deduplicate by id while preserving order.
            seen: set[str] = set()
            unique: list[Recipe] = []
            for r in recipes:
                if r.id in seen:
                    continue
                seen.add(r.id)
                unique.append(r)

            after_profile = [r for r in unique if _passes_profile(r, context)]
            batch_lo_before = [
                r
                for r in after_profile
                if r.batch_friendly and r.leftover_friendly and r.requires_cooking
            ]
            after_time = [r for r in after_profile if _passes_time(r, max_time)]
            batch_lo_after = [
                r
                for r in after_time
                if r.batch_friendly and r.leftover_friendly and r.requires_cooking
            ]
            nocook = [r for r in after_time if not r.requires_cooking]
            min_t = None
            if batch_lo_before:
                min_t = min(int(r.total_time_minutes) for r in batch_lo_before)

            out[mt] = {
                "total": len(unique),
                "after_profile": len(after_profile),
                "after_time": len(after_time),
                "batch_lo_before_time": len(batch_lo_before),
                "batch_lo_after_time": len(batch_lo_after),
                "nocook_after_time": len(nocook),
                "min_batch_lo_time": min_t,
            }
        return out

    @staticmethod
    def _preceding_cook_day(day: int, cook_days: set[int]) -> int | None:
        earlier = [d for d in cook_days if d < day]
        return max(earlier) if earlier else None

    @staticmethod
    def _dedupe_suggestions(
        items: list[SuggestedAdjustment],
    ) -> list[SuggestedAdjustment]:
        seen: set[tuple[Any, ...]] = set()
        out: list[SuggestedAdjustment] = []
        for item in items:
            key = (
                item.suggestion,
                item.day,
                item.current,
                item.minimum_supported,
                item.reason,
            )
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @staticmethod
    def _dedupe_issues(items: list[FeasibilityIssue]) -> list[FeasibilityIssue]:
        seen: set[tuple[Any, ...]] = set()
        out: list[FeasibilityIssue] = []
        for item in items:
            key = (item.code, item.target_slot, item.source_cook_day, item.meal_type)
            if key in seen:
                continue
            seen.add(key)
            out.append(item)
        return out

    @staticmethod
    def _warning_ru(
        *,
        status: FeasibilityStatus,
        strategy: WeeklyStrategy,
        max_time: int | None,
        issues: list[FeasibilityIssue],
        non_cook_days: list[int],
    ) -> str | None:
        if status == FeasibilityStatus.FEASIBLE:
            return None
        cook = ", ".join(str(d) for d in strategy.cook_days) or "все дни"
        ctl = max_time if max_time is not None else strategy.cooking_time_limit
        if status == FeasibilityStatus.FEASIBLE_WITH_RELAXATION:
            return (
                f"При готовке в дни [{cook}] и лимите {ctl} мин. может понадобиться "
                f"один дополнительный день готовки вне cook_days."
            )
        # INFEASIBLE
        has_time_gap = any(
            i.code == FeasibilityIssueCode.TIME_LIMIT_REMOVES_REQUIRED_BATCH_CANDIDATES.value
            for i in issues
        )
        if has_time_gap:
            return (
                f"При готовке только в дни [{cook}] и лимите {ctl} минут не хватает "
                f"быстрых блюд, которые можно приготовить заранее для ужина/обеда "
                f"следующего дня (дни без готовки: {non_cook_days})."
            )
        return (
            f"Стратегия готовки в дни [{cook}] при лимите {ctl} мин. несовместима "
            f"с текущим каталогом для дней без готовки {non_cook_days}."
        )
