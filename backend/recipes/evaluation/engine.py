"""Run evaluation scenarios against RecipeCandidateSelector."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from recipes.enums import MealType, RecipeStatus
from recipes.evaluation.gap_analyzer import CatalogGapAnalyzer
from recipes.evaluation.loader import load_evaluation_scenarios
from recipes.evaluation.models import (
    CatalogCoverageReport,
    EvaluationScenario,
    EvaluationScenarioResult,
    ScenarioCoverageStatus,
)
from recipes.evaluation.recommendations import build_recommendations
from recipes.models import Recipe
from recipes.repository import RecipeRepository
from recipes.selection.selector import RecipeCandidateSelector


def _coverage_ratio(actual: int, expected: int) -> float:
    if expected <= 0:
        return 1.0
    return min(1.0, actual / expected)


def _status(actual: int, expected: int) -> ScenarioCoverageStatus:
    if expected == 0 and actual == 0:
        return ScenarioCoverageStatus.EXPECTED_EMPTY
    if expected == 0 and actual > 0:
        return ScenarioCoverageStatus.EXPECTED_EMPTY
    if actual <= 0:
        return ScenarioCoverageStatus.CRITICAL
    if actual < expected:
        return ScenarioCoverageStatus.WEAK
    return ScenarioCoverageStatus.COVERED


def _time_bucket(minutes: int | None) -> str:
    if minutes is None:
        return "none"
    if minutes <= 10:
        return "le_10"
    if minutes <= 15:
        return "le_15"
    if minutes <= 20:
        return "le_20"
    if minutes <= 30:
        return "le_30"
    if minutes <= 45:
        return "le_45"
    return "gt_45"


def _weighted_avg(pairs: list[tuple[float, float]]) -> float:
    if not pairs:
        return 0.0
    num = sum(ratio * weight for ratio, weight in pairs)
    den = sum(weight for _, weight in pairs)
    return num / den if den else 0.0


class CatalogEvaluator:
    def __init__(
        self,
        repository: RecipeRepository | None = None,
        *,
        db_path: Path | str | None = None,
        selector: RecipeCandidateSelector | None = None,
    ) -> None:
        self.repository = repository or RecipeRepository(db_path)
        self.selector = selector or RecipeCandidateSelector(repository=self.repository)

    async def _preload_catalog(self) -> tuple[list[Recipe], int]:
        # Load all meal-type pools once and merge by id.
        by_id: dict[str, Recipe] = {}
        for meal in (MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER, MealType.SNACK):
            rows = await self.repository.find_candidate_recipes_with_deps(meal_type=meal)
            for recipe in rows:
                by_id[recipe.id] = recipe
        # Also include any active recipes missing meal_type links via list_active + hydrate
        active = await self.repository.list_active()
        for stub in active:
            if stub.id not in by_id:
                full = await self.repository.get_recipe_with_dependencies(stub.id)
                if full is not None:
                    by_id[full.id] = full
        recipes = sorted(by_id.values(), key=lambda r: r.id)
        total = await self.repository.count_recipes(RecipeStatus.ACTIVE)
        return recipes, total

    async def evaluate_scenario(
        self,
        scenario: EvaluationScenario,
        *,
        recipe_pool: list[Recipe],
        total_catalog: int,
    ) -> EvaluationScenarioResult:
        result = await self.selector.select(
            scenario.context,
            recipe_pool=recipe_pool,
            total_catalog_recipes=total_catalog,
        )
        actual = result.after_hard_filters
        scores = [c.score for c in result.candidates]
        removed = result.filter_stats.removed or {}
        dominant = sorted(removed.keys(), key=lambda k: (-removed[k], k))[:5]

        return EvaluationScenarioResult(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            scenario_group=scenario.scenario_group,
            expected_min_candidates=scenario.expected_min_candidates,
            actual_candidates=actual,
            coverage_ratio=_coverage_ratio(actual, scenario.expected_min_candidates),
            status=_status(actual, scenario.expected_min_candidates),
            selection_status=result.selection_status.value,
            top_candidate_ids=[c.recipe.id for c in result.candidates],
            top_candidate_names=[c.recipe.name for c in result.candidates],
            filter_stats=result.filter_stats.to_dict(),
            dominant_filter_reasons=dominant,
            average_score=(sum(scores) / len(scores)) if scores else None,
            minimum_score=min(scores) if scores else None,
            maximum_score=max(scores) if scores else None,
            score_spread=(max(scores) - min(scores)) if len(scores) > 1 else (
                0.0 if scores else None
            ),
            weight=scenario.weight,
            meal_type=scenario.context.meal_type.value,
            goal=scenario.context.goal.value if scenario.context.goal else None,
            max_total_time_minutes=scenario.context.max_total_time_minutes,
            allowed_budget_classes=(
                [b.value for b in scenario.context.allowed_budget_classes]
                if scenario.context.allowed_budget_classes is not None
                else None
            ),
        )

    async def evaluate(
        self,
        scenarios: list[EvaluationScenario] | None = None,
        *,
        evaluation_dir: Path | None = None,
        scenario_file: Path | None = None,
        group: str | None = None,
        schema_version: str = "1",
    ) -> CatalogCoverageReport:
        if scenarios is None:
            scenarios = load_evaluation_scenarios(
                evaluation_dir, scenario_file=scenario_file, group=group
            )

        recipe_pool, total = await self._preload_catalog()
        results: list[EvaluationScenarioResult] = []
        for scenario in scenarios:
            results.append(
                await self.evaluate_scenario(
                    scenario,
                    recipe_pool=recipe_pool,
                    total_catalog=total,
                )
            )

        results.sort(key=lambda r: (r.scenario_group.value, r.scenario_id))

        covered = sum(1 for r in results if r.status == ScenarioCoverageStatus.COVERED)
        weak = sum(1 for r in results if r.status == ScenarioCoverageStatus.WEAK)
        critical = sum(1 for r in results if r.status == ScenarioCoverageStatus.CRITICAL)
        expected_empty = sum(
            1 for r in results if r.status == ScenarioCoverageStatus.EXPECTED_EMPTY
        )

        weighted = _weighted_avg([(r.coverage_ratio, r.weight) for r in results])

        by_meal: dict[str, list[tuple[float, float]]] = defaultdict(list)
        by_goal: dict[str, list[tuple[float, float]]] = defaultdict(list)
        by_group: dict[str, list[tuple[float, float]]] = defaultdict(list)
        by_budget: dict[str, list[tuple[float, float]]] = defaultdict(list)
        by_time: dict[str, list[tuple[float, float]]] = defaultdict(list)

        filter_removed_total: dict[str, int] = defaultdict(int)
        filter_scenario_hits: dict[str, int] = defaultdict(int)

        for r in results:
            pair = (r.coverage_ratio, r.weight)
            if r.meal_type:
                by_meal[r.meal_type].append(pair)
            if r.goal:
                by_goal[r.goal].append(pair)
            by_group[r.scenario_group.value].append(pair)
            budget_key = (
                "+".join(sorted(r.allowed_budget_classes))
                if r.allowed_budget_classes
                else "any"
            )
            by_budget[budget_key].append(pair)
            by_time[_time_bucket(r.max_total_time_minutes)].append(pair)

            removed = (r.filter_stats or {}).get("removed") or {}
            for code, count in removed.items():
                filter_removed_total[code] += int(count)
                filter_scenario_hits[code] += 1

        scenarios_by_id = {s.id: s for s in scenarios}
        clusters = CatalogGapAnalyzer().analyze(results, scenarios_by_id)
        recommendations = build_recommendations(
            results, clusters, recipe_pool, scenarios_by_id
        )

        return CatalogCoverageReport(
            total_scenarios=len(results),
            covered_scenarios=covered,
            weak_scenarios=weak,
            critical_scenarios=critical,
            expected_empty_scenarios=expected_empty,
            weighted_coverage_score=weighted,
            coverage_by_meal_type={
                k: _weighted_avg(v) for k, v in sorted(by_meal.items())
            },
            coverage_by_goal={k: _weighted_avg(v) for k, v in sorted(by_goal.items())},
            coverage_by_scenario_group={
                k: _weighted_avg(v) for k, v in sorted(by_group.items())
            },
            coverage_by_budget_restriction={
                k: _weighted_avg(v) for k, v in sorted(by_budget.items())
            },
            coverage_by_time_limit_group={
                k: _weighted_avg(v) for k, v in sorted(by_time.items())
            },
            common_filter_failures=dict(
                sorted(filter_removed_total.items(), key=lambda x: (-x[1], x[0]))
            ),
            common_filter_scenario_hits=dict(
                sorted(filter_scenario_hits.items(), key=lambda x: (-x[1], x[0]))
            ),
            catalog_gap_clusters=clusters,
            recommended_additions=recommendations,
            scenario_results=results,
            catalog_recipe_count=total,
            catalog_schema_version=schema_version,
        )
