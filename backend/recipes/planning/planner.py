"""Beam-search weekly recipe planner."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from recipes.enums import MealType
from recipes.models import Recipe
from recipes.planning.candidate_provider import PlanningCandidateProvider
from recipes.planning.constraints import check_cook_action, check_leftover_action
from recipes.planning.context import WeeklyPlanningContext
from recipes.planning.explanation import build_week_explanation
from recipes.planning.models import (
    CookingInstance,
    PlanDiagnostics,
    PlanStatus,
    WeeklyPlannedMeal,
    WeeklyRecipePlan,
)
from recipes.planning.relations import RelationIndex, build_relation_index
from recipes.planning.slots import WeeklyMealSlot, build_weekly_slots
from recipes.planning.validator import WeeklyRecipePlanValidator
from recipes.planning.weekly_scorer import AssignmentView, WeeklyPlanScorer
from recipes.repository import RecipeRepository
from recipes.selection.models import RecipeCandidate
from recipes.selection.selector import RecipeCandidateSelector


@dataclass
class _CookInst:
    cooking_instance_id: str
    recipe_id: str
    source_slot_id: str
    source_order: int
    servings_cooked: int
    servings_consumed: int
    leftover_slots: list[str] = field(default_factory=list)

    @property
    def remaining(self) -> int:
        return self.servings_cooked - self.servings_consumed


@dataclass
class _Assignment:
    slot: WeeklyMealSlot
    recipe: Recipe
    selector_score: float
    selector_rank: int | None
    selector_reasons: list[str]
    alternatives: list[dict[str, Any]]
    is_leftover: bool
    source_slot_id: str | None
    cooking_instance_id: str
    cook_day_miss: bool
    requires_cooking: bool


@dataclass
class _BeamState:
    assignments: list[_Assignment] = field(default_factory=list)
    cook_instances: dict[str, _CookInst] = field(default_factory=dict)
    independent_cooks: dict[str, int] = field(default_factory=dict)

    def clone(self) -> _BeamState:
        return _BeamState(
            assignments=list(self.assignments),
            cook_instances={
                k: _CookInst(
                    cooking_instance_id=v.cooking_instance_id,
                    recipe_id=v.recipe_id,
                    source_slot_id=v.source_slot_id,
                    source_order=v.source_order,
                    servings_cooked=v.servings_cooked,
                    servings_consumed=v.servings_consumed,
                    leftover_slots=list(v.leftover_slots),
                )
                for k, v in self.cook_instances.items()
            },
            independent_cooks=dict(self.independent_cooks),
        )

    def previous_day_recipe_ids(self, day_index: int) -> set[str]:
        return {
            a.recipe.id
            for a in self.assignments
            if a.slot.day_index == day_index - 1 and not a.is_leftover
        }

    def to_views(self) -> list[AssignmentView]:
        return [
            AssignmentView(
                slot=a.slot,
                recipe=a.recipe,
                selector_score=a.selector_score,
                is_leftover=a.is_leftover,
                cook_day_miss=a.cook_day_miss,
            )
            for a in self.assignments
        ]


def _stable_instance_id(source_slot_id: str, recipe_id: str) -> str:
    return f"cook__{source_slot_id}__{recipe_id}"


def _plan_id(context: WeeklyPlanningContext, meals: list[WeeklyPlannedMeal]) -> str:
    payload = {
        "context": context.fingerprint(),
        "meals": [
            {
                "slot_id": m.slot_id,
                "recipe_id": m.recipe_id,
                "is_leftover": m.is_leftover,
                "cooking_instance_id": m.cooking_instance_id,
                "source_slot_id": m.source_slot_id,
            }
            for m in meals
        ],
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()[:16]
    return f"wrp_{digest}"


class WeeklyRecipePlanner:
    def __init__(
        self,
        *,
        repository: RecipeRepository | None = None,
        selector: RecipeCandidateSelector | None = None,
        candidate_provider: PlanningCandidateProvider | None = None,
        scorer: WeeklyPlanScorer | None = None,
        validator: WeeklyRecipePlanValidator | None = None,
    ) -> None:
        self.repository = repository or RecipeRepository()
        self.selector = selector or RecipeCandidateSelector(repository=self.repository)
        self.candidate_provider = candidate_provider or PlanningCandidateProvider(
            selector=self.selector,
            repository=self.repository,
        )
        self.scorer = scorer or WeeklyPlanScorer()
        self.validator = validator or WeeklyRecipePlanValidator()

    async def plan(self, context: WeeklyPlanningContext) -> WeeklyRecipePlan:
        started = time.perf_counter()
        slots = build_weekly_slots(context)
        diagnostics = PlanDiagnostics(
            candidate_pool_size=context.config.candidate_pool_size,
            beam_width=context.config.beam_width,
        )

        relations = await self.repository.get_relations()
        relation_index = build_relation_index(relations)
        await self.candidate_provider.load_quality_map()

        pools_by_meal: dict[MealType, list[RecipeCandidate]] = {}
        filter_by_meal: dict[MealType, dict[str, int]] = {}
        for meal_type in context.meal_types:
            probe = WeeklyMealSlot(
                day_index=1,
                meal_type=meal_type,
                slot_id=f"probe_{meal_type.value}",
                is_cook_day=True,
                leftovers_allowed=context.leftovers_enabled,
            )
            pool = await self.candidate_provider.candidates_for_slot(context, probe)
            pools_by_meal[meal_type] = pool.candidates
            filter_by_meal[meal_type] = dict(pool.filter_stats)

        beam: list[_BeamState] = [_BeamState()]
        states_expanded = 0
        states_pruned = 0
        slot_causes: dict[str, dict[str, int]] = {}

        for slot in slots:
            candidates = pools_by_meal.get(slot.meal_type, [])
            slot_causes[slot.slot_id] = dict(filter_by_meal.get(slot.meal_type, {}))
            next_beam: list[_BeamState] = []

            for state in beam:
                actions = self._actions_for_slot(
                    state=state,
                    slot=slot,
                    context=context,
                    relation_index=relation_index,
                    pool_candidates=candidates,
                )
                if not actions:
                    states_pruned += 1
                    continue
                for action in actions:
                    if states_expanded >= context.config.max_states:
                        break
                    states_expanded += 1
                    nxt = state.clone()
                    self._apply_action(nxt, slot, action, context)
                    next_beam.append(nxt)
                if states_expanded >= context.config.max_states:
                    break

            if not next_beam:
                diagnostics.states_expanded = states_expanded
                diagnostics.states_pruned = states_pruned
                diagnostics.slot_filter_causes = slot_causes
                diagnostics.unfilled_slots = [
                    s.slot_id for s in slots if s.order_index >= slot.order_index
                ]
                diagnostics.planning_duration_ms = (
                    time.perf_counter() - started
                ) * 1000
                best = max(beam, key=lambda s: len(s.assignments)) if beam else _BeamState()
                return self._finalize(
                    context=context,
                    state=best,
                    slots=slots,
                    relation_index=relation_index,
                    diagnostics=diagnostics,
                    force_status=PlanStatus.NO_PLAN
                    if not best.assignments
                    else PlanStatus.PARTIAL,
                )

            ranked: list[tuple[tuple, _BeamState]] = []
            for st in next_beam:
                score, _, _ = self.scorer.score_plan(
                    assignments=st.to_views(),
                    context=context,
                    relation_index=relation_index,
                )
                ids = tuple(
                    (
                        a.slot.slot_id,
                        a.recipe.id,
                        a.is_leftover,
                        a.cooking_instance_id,
                    )
                    for a in st.assignments
                )
                ranked.append(((-score, ids), st))
            ranked.sort(key=lambda x: x[0])
            keep = ranked[: context.config.beam_width]
            states_pruned += max(0, len(ranked) - len(keep))
            beam = [st for _, st in keep]

            if states_expanded >= context.config.max_states:
                break

        diagnostics.states_expanded = states_expanded
        diagnostics.states_pruned = states_pruned
        diagnostics.slot_filter_causes = slot_causes
        diagnostics.planning_duration_ms = (time.perf_counter() - started) * 1000

        if not beam or len(beam[0].assignments) < len(slots):
            best = beam[0] if beam else _BeamState()
            filled = {a.slot.slot_id for a in best.assignments}
            diagnostics.unfilled_slots = [s.slot_id for s in slots if s.slot_id not in filled]
            return self._finalize(
                context=context,
                state=best,
                slots=slots,
                relation_index=relation_index,
                diagnostics=diagnostics,
                force_status=PlanStatus.PARTIAL if best.assignments else PlanStatus.NO_PLAN,
            )

        return self._finalize(
            context=context,
            state=beam[0],
            slots=slots,
            relation_index=relation_index,
            diagnostics=diagnostics,
            force_status=None,
        )

    def _actions_for_slot(
        self,
        *,
        state: _BeamState,
        slot: WeeklyMealSlot,
        context: WeeklyPlanningContext,
        relation_index: RelationIndex,
        pool_candidates: list[RecipeCandidate],
    ) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        cfg = context.config
        leftover_available = False

        if context.leftovers_enabled and slot.leftovers_allowed:
            for inst_id in sorted(state.cook_instances.keys()):
                inst = state.cook_instances[inst_id]
                if inst.remaining <= 0:
                    continue
                src = next(
                    (
                        a
                        for a in state.assignments
                        if a.slot.slot_id == inst.source_slot_id
                    ),
                    None,
                )
                if src is None or not src.recipe.leftover_friendly:
                    continue
                recipe = src.recipe
                fail = check_leftover_action(
                    recipe=recipe,
                    slot=slot,
                    context=context,
                    source_slot_order=inst.source_order,
                    slot_order=slot.order_index,
                    remaining_servings=inst.remaining,
                )
                if fail:
                    continue
                leftover_available = True
                actions.append(
                    {
                        "kind": "leftover",
                        "recipe": recipe,
                        "selector_score": src.selector_score * 0.95,
                        "selector_rank": None,
                        "selector_reasons": list(src.selector_reasons),
                        "alternatives": [],
                        "instance_id": inst_id,
                        "source_slot_id": inst.source_slot_id,
                    }
                )

        alts = [
            {"recipe_id": c.recipe.id, "score": round(c.score, 4), "rank": i + 1}
            for i, c in enumerate(pool_candidates[:5])
        ]
        for rank, cand in enumerate(pool_candidates, start=1):
            recipe = cand.recipe
            fail = check_cook_action(
                recipe=recipe,
                slot=slot,
                context=context,
                config=cfg,
                relation_index=relation_index,
                previous_day_recipe_ids=state.previous_day_recipe_ids(slot.day_index),
                independent_cook_counts=state.independent_cooks,
            )
            if fail:
                continue
            cook_day_miss = bool(recipe.requires_cooking and not slot.is_cook_day)
            if cook_day_miss and not cfg.allow_cook_day_miss:
                continue
            if (
                not slot.is_cook_day
                and cfg.prefer_leftovers_on_non_cook_days
                and leftover_available
                and cook_day_miss
            ):
                # Still allow as escape hatch but deprioritize via sort / score.
                pass
            actions.append(
                {
                    "kind": "cook",
                    "recipe": recipe,
                    "selector_score": cand.score,
                    "selector_rank": rank,
                    "selector_reasons": list(cand.reason_codes),
                    "alternatives": [a for a in alts if a["recipe_id"] != recipe.id][:3],
                    "cook_day_miss": cook_day_miss,
                }
            )

        def sort_key(a: dict[str, Any]) -> tuple:
            if a["kind"] == "leftover":
                # Prefer leftovers on non-cook days
                group = 0 if not slot.is_cook_day else 2
            else:
                miss = 1 if a.get("cook_day_miss") else 0
                group = 1 + miss
            return (group, -float(a["selector_score"]), a["recipe"].id)

        actions.sort(key=sort_key)
        return actions

    def _apply_action(
        self,
        state: _BeamState,
        slot: WeeklyMealSlot,
        action: dict[str, Any],
        context: WeeklyPlanningContext,
    ) -> None:
        recipe: Recipe = action["recipe"]
        if action["kind"] == "leftover":
            inst = state.cook_instances[action["instance_id"]]
            inst.servings_consumed += 1
            inst.leftover_slots.append(slot.slot_id)
            state.assignments.append(
                _Assignment(
                    slot=slot,
                    recipe=recipe,
                    selector_score=float(action["selector_score"]),
                    selector_rank=None,
                    selector_reasons=list(action["selector_reasons"]),
                    alternatives=[],
                    is_leftover=True,
                    source_slot_id=action["source_slot_id"],
                    cooking_instance_id=action["instance_id"],
                    cook_day_miss=False,
                    requires_cooking=False,
                )
            )
            return

        servings = 1
        if (
            context.leftovers_enabled
            and recipe.batch_friendly
            and recipe.leftover_friendly
            and slot.meal_type != MealType.BREAKFAST
        ):
            servings = 1 + context.config.max_leftovers_per_cook

        inst_id = _stable_instance_id(slot.slot_id, recipe.id)
        state.cook_instances[inst_id] = _CookInst(
            cooking_instance_id=inst_id,
            recipe_id=recipe.id,
            source_slot_id=slot.slot_id,
            source_order=slot.order_index,
            servings_cooked=servings,
            servings_consumed=1,
        )
        state.independent_cooks[recipe.id] = (
            state.independent_cooks.get(recipe.id, 0) + 1
        )
        state.assignments.append(
            _Assignment(
                slot=slot,
                recipe=recipe,
                selector_score=float(action["selector_score"]),
                selector_rank=action.get("selector_rank"),
                selector_reasons=list(action["selector_reasons"]),
                alternatives=list(action.get("alternatives") or []),
                is_leftover=False,
                source_slot_id=None,
                cooking_instance_id=inst_id,
                cook_day_miss=bool(action.get("cook_day_miss")),
                requires_cooking=True,
            )
        )

    def _finalize(
        self,
        *,
        context: WeeklyPlanningContext,
        state: _BeamState,
        slots: list[WeeklyMealSlot],
        relation_index: RelationIndex,
        diagnostics: PlanDiagnostics,
        force_status: PlanStatus | None,
    ) -> WeeklyRecipePlan:
        score, breakdown, reason_map = self.scorer.score_plan(
            assignments=state.to_views(),
            context=context,
            relation_index=relation_index,
        )
        meals: list[WeeklyPlannedMeal] = []
        for a in state.assignments:
            meals.append(
                WeeklyPlannedMeal(
                    slot_id=a.slot.slot_id,
                    day_index=a.slot.day_index,
                    meal_type=a.slot.meal_type.value,
                    recipe_id=a.recipe.id,
                    recipe_name=a.recipe.name,
                    selection_score=a.selector_score,
                    selector_rank=a.selector_rank,
                    is_leftover=a.is_leftover,
                    source_slot_id=a.source_slot_id,
                    cooking_instance_id=a.cooking_instance_id,
                    requires_cooking=a.requires_cooking,
                    selector_reasons=list(a.selector_reasons),
                    planner_reasons=list(reason_map.get(a.slot.slot_id, [])),
                    alternatives=list(a.alternatives),
                )
            )
        cooking_instances = [
            CookingInstance(
                cooking_instance_id=c.cooking_instance_id,
                recipe_id=c.recipe_id,
                source_slot_id=c.source_slot_id,
                servings_cooked=c.servings_cooked,
                servings_consumed=c.servings_consumed,
                leftover_slots=list(c.leftover_slots),
            )
            for c in sorted(
                state.cook_instances.values(), key=lambda x: x.cooking_instance_id
            )
        ]

        if force_status is not None:
            status = force_status
        elif len(meals) == len(slots):
            status = PlanStatus.SUCCESS
        elif meals:
            status = PlanStatus.PARTIAL
        else:
            status = PlanStatus.NO_PLAN

        plan = WeeklyRecipePlan(
            plan_id=_plan_id(context, meals),
            status=status,
            strategy_id=context.strategy_id,
            days=context.days,
            meal_types=[m.value for m in context.meal_types],
            meals=meals,
            cooking_instances=cooking_instances,
            score=score,
            score_breakdown=breakdown,
            explanation={},
            diagnostics=diagnostics,
            warnings=list(diagnostics.warnings),
        )
        plan.explanation = build_week_explanation(plan, context)
        recipes = {a.recipe.id: a.recipe for a in state.assignments}
        report = self.validator.validate(
            plan,
            context=context,
            recipes=recipes,
            relation_index=relation_index,
            slots=slots,
        )
        plan.violations = [v.model_dump() for v in report.violations]
        if report.violations and plan.status == PlanStatus.SUCCESS:
            plan.warnings.append("validator_reported_issues")
            plan.diagnostics.warnings.append("validator_reported_issues")
        return plan
