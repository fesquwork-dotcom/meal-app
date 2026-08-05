"""Beam-search weekly recipe planner."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any

from recipes.enums import MealType
from recipes.models import Recipe
from recipes.planning.candidate_provider import PlanningCandidateProvider
from recipes.planning.constraints import check_cook_action, check_leftover_action
from recipes.planning.context import WeeklyPlanningContext
from recipes.planning.diagnostics import (
    PlannerDiagnostics,
    RejectedCandidate,
    SlotDiagnostics,
    TerminationReason,
    infer_termination_reason,
    map_reject_reason,
    merge_counts,
    top_rejected,
)
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

logger = logging.getLogger(__name__)


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
    # Unique day_index values with new cooking outside preferred cook_days.
    extra_cook_days: set[int] = field(default_factory=set)

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
            extra_cook_days=set(self.extra_cook_days),
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


@dataclass
class SlotActionStats:
    """Side-channel stats from action enumeration (does not affect actions)."""

    candidate_count_before_filters: int = 0
    candidate_count_after_hard_filters: int = 0
    candidate_count_after_weekly_constraints: int = 0
    candidate_count_after_ranking: int = 0
    hard_filter_removals: dict[str, int] = field(default_factory=dict)
    weekly_constraint_removals: dict[str, int] = field(default_factory=dict)
    rejected_candidates: list[RejectedCandidate] = field(default_factory=list)
    candidate_evaluations: int = 0
    constraint_evaluations: int = 0


@dataclass
class _MealPoolMeta:
    candidates: list[RecipeCandidate]
    filter_stats: dict[str, int]
    before_filters: int
    after_hard_filters: int
    quality_removed: int


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


def _partial_plan_from_state(
    state: _BeamState, *, score: float | None = None
) -> dict[str, Any]:
    return {
        "score": score,
        "assignments": [
            {
                "slot_id": a.slot.slot_id,
                "recipe_id": a.recipe.id,
                "is_leftover": a.is_leftover,
            }
            for a in state.assignments
        ],
    }


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
            slots_total=len(slots),
        )

        relations = await self.repository.get_relations()
        relation_index = build_relation_index(relations)
        await self.candidate_provider.load_quality_map()

        pools_by_meal: dict[MealType, _MealPoolMeta] = {}
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
            sel = pool.selection_result
            before = int(sel.total_catalog_recipes) if sel is not None else 0
            # Quality filter applied after selector; count removals for diagnostics.
            raw_candidates = list(sel.candidates) if sel is not None else list(
                pool.candidates
            )
            quality_removed = max(0, len(raw_candidates) - len(pool.candidates))
            hard_stats = dict(pool.filter_stats)
            if quality_removed:
                hard_stats["QUALITY_BELOW_MINIMUM"] = (
                    int(hard_stats.get("QUALITY_BELOW_MINIMUM", 0)) + quality_removed
                )
            pools_by_meal[meal_type] = _MealPoolMeta(
                candidates=pool.candidates,
                filter_stats=hard_stats,
                before_filters=before,
                after_hard_filters=len(pool.candidates),
                quality_removed=quality_removed,
            )
            filter_by_meal[meal_type] = dict(hard_stats)

        beam: list[_BeamState] = [_BeamState()]
        states_expanded = 0
        states_pruned = 0
        slot_causes: dict[str, dict[str, int]] = {}
        slot_diags: list[SlotDiagnostics] = []
        hard_filter_agg: dict[str, int] = {}
        constraint_agg: dict[str, int] = {}
        beam_iterations = 0
        max_queue_size = 1
        visited_states = 0
        candidate_evaluations = 0
        constraint_evaluations = 0
        ranking_evaluations = 0
        max_states_hit = False
        failed_slot_id: str | None = None
        last_successful_slot: str | None = None
        stop_early = False

        for slot in slots:
            meal_meta = pools_by_meal.get(slot.meal_type)
            candidates = meal_meta.candidates if meal_meta else []
            hard_stats = (
                dict(meal_meta.filter_stats)
                if meal_meta
                else dict(filter_by_meal.get(slot.meal_type, {}))
            )
            slot_causes[slot.slot_id] = dict(hard_stats)
            merge_counts(hard_filter_agg, hard_stats)

            next_beam: list[_BeamState] = []
            slot_weekly: dict[str, int] = {}
            slot_rejected: list[RejectedCandidate] = []
            slot_after_weekly = 0
            slot_cand_evals = 0
            slot_constraint_evals = 0
            visited_states += len(beam)
            max_queue_size = max(max_queue_size, len(beam))
            beam_iterations += 1

            for state in beam:
                actions, action_stats = self._actions_for_slot(
                    state=state,
                    slot=slot,
                    context=context,
                    relation_index=relation_index,
                    pool_candidates=candidates,
                    hard_filter_removals=hard_stats,
                    before_filters=(
                        meal_meta.before_filters if meal_meta else 0
                    ),
                    after_hard_filters=(
                        meal_meta.after_hard_filters
                        if meal_meta
                        else len(candidates)
                    ),
                )
                merge_counts(slot_weekly, action_stats.weekly_constraint_removals)
                merge_counts(constraint_agg, action_stats.weekly_constraint_removals)
                slot_rejected.extend(action_stats.rejected_candidates)
                slot_after_weekly = max(
                    slot_after_weekly,
                    action_stats.candidate_count_after_weekly_constraints,
                )
                slot_cand_evals += action_stats.candidate_evaluations
                slot_constraint_evals += action_stats.constraint_evaluations
                candidate_evaluations += action_stats.candidate_evaluations
                constraint_evaluations += action_stats.constraint_evaluations

                if not actions:
                    states_pruned += 1
                    continue
                for action in actions:
                    if states_expanded >= context.config.max_states:
                        max_states_hit = True
                        break
                    states_expanded += 1
                    nxt = state.clone()
                    self._apply_action(nxt, slot, action, context)
                    next_beam.append(nxt)
                if states_expanded >= context.config.max_states:
                    max_states_hit = True
                    break

            slot_diag = SlotDiagnostics(
                slot_id=slot.slot_id,
                meal_type=slot.meal_type.value,
                day_index=slot.day_index,
                is_cook_day=slot.is_cook_day,
                filled=bool(next_beam),
                selected_recipe_id=None,
                failure_reason=None if next_beam else "no_viable_actions",
                candidate_count_before_filters=(
                    meal_meta.before_filters if meal_meta else 0
                ),
                candidate_count_after_hard_filters=(
                    meal_meta.after_hard_filters if meal_meta else len(candidates)
                ),
                candidate_count_after_weekly_constraints=slot_after_weekly,
                candidate_count_after_ranking=slot_after_weekly,
                hard_filter_removals=dict(hard_stats),
                weekly_constraint_removals=dict(slot_weekly),
                best_failed_candidates=top_rejected(slot_rejected, limit=5),
            )

            if not next_beam:
                failed_slot_id = slot.slot_id
                slot_diags.append(slot_diag)
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
                self._populate_search_metrics(
                    diagnostics,
                    beam_iterations=beam_iterations,
                    max_queue_size=max_queue_size,
                    visited_states=visited_states,
                    states_expanded=states_expanded,
                    states_pruned=states_pruned,
                    final_queue_size=len(beam),
                    candidate_evaluations=candidate_evaluations,
                    constraint_evaluations=constraint_evaluations,
                    ranking_evaluations=ranking_evaluations,
                    hard_filter_agg=hard_filter_agg,
                    constraint_agg=constraint_agg,
                    slot_diags=slot_diags,
                    failed_slot=failed_slot_id,
                    last_successful_slot=last_successful_slot,
                    max_states_hit=max_states_hit,
                    best_state=best,
                    context=context,
                    relation_index=relation_index,
                )
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
                ranking_evaluations += 1
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
            max_queue_size = max(max_queue_size, len(beam))

            # Record selected recipe from best surviving state for this slot.
            if beam:
                chosen = next(
                    (a for a in beam[0].assignments if a.slot.slot_id == slot.slot_id),
                    None,
                )
                if chosen is not None:
                    slot_diag.filled = True
                    slot_diag.selected_recipe_id = chosen.recipe.id
                    slot_diag.selected = chosen.recipe.id
                    slot_diag.failure_reason = None
            slot_diags.append(slot_diag)
            last_successful_slot = slot.slot_id

            if states_expanded >= context.config.max_states:
                max_states_hit = True
                stop_early = True
                break

        diagnostics.states_expanded = states_expanded
        diagnostics.states_pruned = states_pruned
        diagnostics.slot_filter_causes = slot_causes
        diagnostics.planning_duration_ms = (time.perf_counter() - started) * 1000

        if not beam or len(beam[0].assignments) < len(slots):
            best = beam[0] if beam else _BeamState()
            filled = {a.slot.slot_id for a in best.assignments}
            diagnostics.unfilled_slots = [s.slot_id for s in slots if s.slot_id not in filled]
            if diagnostics.unfilled_slots and failed_slot_id is None:
                failed_slot_id = diagnostics.unfilled_slots[0]
            self._populate_search_metrics(
                diagnostics,
                beam_iterations=beam_iterations,
                max_queue_size=max_queue_size,
                visited_states=visited_states,
                states_expanded=states_expanded,
                states_pruned=states_pruned,
                final_queue_size=len(beam),
                candidate_evaluations=candidate_evaluations,
                constraint_evaluations=constraint_evaluations,
                ranking_evaluations=ranking_evaluations,
                hard_filter_agg=hard_filter_agg,
                constraint_agg=constraint_agg,
                slot_diags=slot_diags,
                failed_slot=failed_slot_id,
                last_successful_slot=last_successful_slot,
                max_states_hit=max_states_hit or stop_early,
                best_state=best,
                context=context,
                relation_index=relation_index,
            )
            return self._finalize(
                context=context,
                state=best,
                slots=slots,
                relation_index=relation_index,
                diagnostics=diagnostics,
                force_status=PlanStatus.PARTIAL if best.assignments else PlanStatus.NO_PLAN,
            )

        self._populate_search_metrics(
            diagnostics,
            beam_iterations=beam_iterations,
            max_queue_size=max_queue_size,
            visited_states=visited_states,
            states_expanded=states_expanded,
            states_pruned=states_pruned,
            final_queue_size=len(beam),
            candidate_evaluations=candidate_evaluations,
            constraint_evaluations=constraint_evaluations,
            ranking_evaluations=ranking_evaluations,
            hard_filter_agg=hard_filter_agg,
            constraint_agg=constraint_agg,
            slot_diags=slot_diags,
            failed_slot=None,
            last_successful_slot=last_successful_slot,
            max_states_hit=False,
            best_state=beam[0],
            context=context,
            relation_index=relation_index,
        )
        return self._finalize(
            context=context,
            state=beam[0],
            slots=slots,
            relation_index=relation_index,
            diagnostics=diagnostics,
            force_status=None,
        )

    def _populate_search_metrics(
        self,
        diagnostics: PlannerDiagnostics,
        *,
        beam_iterations: int,
        max_queue_size: int,
        visited_states: int,
        states_expanded: int,
        states_pruned: int,
        final_queue_size: int,
        candidate_evaluations: int,
        constraint_evaluations: int,
        ranking_evaluations: int,
        hard_filter_agg: dict[str, int],
        constraint_agg: dict[str, int],
        slot_diags: list[SlotDiagnostics],
        failed_slot: str | None,
        last_successful_slot: str | None,
        max_states_hit: bool,
        best_state: _BeamState,
        context: WeeklyPlanningContext,
        relation_index: RelationIndex,
    ) -> None:
        diagnostics.expanded_states = states_expanded
        diagnostics.pruned_states = states_pruned
        diagnostics.visited_states = visited_states
        diagnostics.beam_iterations = beam_iterations
        diagnostics.slots_completed = sum(1 for s in slot_diags if s.filled)
        diagnostics.failed_slot = failed_slot
        diagnostics.last_successful_slot = last_successful_slot
        diagnostics.hard_filter_stats = dict(hard_filter_agg)
        diagnostics.constraint_statistics = dict(constraint_agg)
        diagnostics.slots = list(slot_diags)

        failed_diag = next(
            (s for s in slot_diags if s.slot_id == failed_slot), None
        )
        if failed_diag is not None:
            diagnostics.best_failed_candidates = list(
                failed_diag.best_failed_candidates
            )

        score: float | None = None
        if best_state.assignments:
            score, _, _ = self.scorer.score_plan(
                assignments=best_state.to_views(),
                context=context,
                relation_index=relation_index,
            )
            diagnostics.best_partial_score = float(score)
        diagnostics.partial_plan = _partial_plan_from_state(best_state, score=score)

        diagnostics.beam_metrics = {
            "beam_width": diagnostics.beam_width,
            "iterations": beam_iterations,
            "max_queue": max_queue_size,
            "visited": visited_states,
            "expanded": states_expanded,
            "pruned": states_pruned,
            "final_queue_size": final_queue_size,
            "max_states_hit": max_states_hit,
        }
        diagnostics.search_complexity = {
            "candidate_evaluations": candidate_evaluations,
            "constraint_evaluations": constraint_evaluations,
            "ranking_evaluations": ranking_evaluations,
            "planning_duration_ms": diagnostics.planning_duration_ms,
        }
        diagnostics.candidate_statistics = {
            "pool_size": diagnostics.candidate_pool_size,
            "hard_filter_stats": dict(hard_filter_agg),
            "slots": [
                {
                    "slot_id": s.slot_id,
                    "before": s.candidate_count_before_filters,
                    "after_hard": s.candidate_count_after_hard_filters,
                    "after_weekly": s.candidate_count_after_weekly_constraints,
                    "filled": s.filled,
                }
                for s in slot_diags
            ],
        }

        # Provisional status for termination inference; finalized in _finalize.
        provisional = (
            "success"
            if failed_slot is None and len(best_state.assignments) == diagnostics.slots_total
            else ("partial" if best_state.assignments else "no_plan")
        )
        reason = infer_termination_reason(
            planning_status=provisional,
            failed_slot=failed_diag,
            max_states_hit=max_states_hit,
            is_cook_day=failed_diag.is_cook_day if failed_diag else None,
        )
        diagnostics.termination_reason = reason.value
        if max_states_hit and provisional != "success":
            diagnostics.planner_notes.append("max_states_cutoff")
        if failed_slot:
            diagnostics.planner_notes.append(f"failed_at={failed_slot}")

    def _actions_for_slot(
        self,
        *,
        state: _BeamState,
        slot: WeeklyMealSlot,
        context: WeeklyPlanningContext,
        relation_index: RelationIndex,
        pool_candidates: list[RecipeCandidate],
        hard_filter_removals: dict[str, int] | None = None,
        before_filters: int = 0,
        after_hard_filters: int = 0,
    ) -> tuple[list[dict[str, Any]], SlotActionStats]:
        actions: list[dict[str, Any]] = []
        cfg = context.config
        leftover_available = False
        stats = SlotActionStats(
            candidate_count_before_filters=before_filters,
            candidate_count_after_hard_filters=after_hard_filters
            or len(pool_candidates),
            hard_filter_removals=dict(hard_filter_removals or {}),
        )

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
                stats.constraint_evaluations += 1
                fail = check_leftover_action(
                    recipe=recipe,
                    slot=slot,
                    context=context,
                    source_slot_order=inst.source_order,
                    slot_order=slot.order_index,
                    remaining_servings=inst.remaining,
                )
                if fail:
                    reason = map_reject_reason(str(fail.code))
                    stats.weekly_constraint_removals[reason] = (
                        int(stats.weekly_constraint_removals.get(reason, 0)) + 1
                    )
                    stats.rejected_candidates.append(
                        RejectedCandidate(
                            recipe_id=recipe.id,
                            selector_score=float(src.selector_score),
                            reject_reason=reason,
                            detail=fail.detail or "",
                        )
                    )
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
            stats.candidate_evaluations += 1
            stats.constraint_evaluations += 1
            fail = check_cook_action(
                recipe=recipe,
                slot=slot,
                context=context,
                config=cfg,
                relation_index=relation_index,
                previous_day_recipe_ids=state.previous_day_recipe_ids(slot.day_index),
                independent_cook_counts=state.independent_cooks,
                extra_cook_days=state.extra_cook_days,
            )
            if fail:
                reason = map_reject_reason(str(fail.code))
                stats.weekly_constraint_removals[reason] = (
                    int(stats.weekly_constraint_removals.get(reason, 0)) + 1
                )
                stats.rejected_candidates.append(
                    RejectedCandidate(
                        recipe_id=recipe.id,
                        selector_score=float(cand.score),
                        reject_reason=reason,
                        detail=fail.detail or "",
                    )
                )
                continue
            cook_day_miss = bool(recipe.requires_cooking and not slot.is_cook_day)
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
        stats.candidate_count_after_weekly_constraints = len(actions)
        stats.candidate_count_after_ranking = len(actions)
        return actions, stats

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
        cook_day_miss = bool(action.get("cook_day_miss"))
        if cook_day_miss:
            state.extra_cook_days.add(slot.day_index)
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
                cook_day_miss=cook_day_miss,
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

        diagnostics.planning_status = status.value
        if status == PlanStatus.SUCCESS:
            diagnostics.termination_reason = TerminationReason.SUCCESS.value
            diagnostics.failed_slot = None
            diagnostics.unfilled_slots = []
        elif diagnostics.termination_reason in {
            TerminationReason.UNKNOWN.value,
            "",
        }:
            failed_diag = next(
                (s for s in diagnostics.slots if s.slot_id == diagnostics.failed_slot),
                None,
            )
            diagnostics.termination_reason = infer_termination_reason(
                planning_status=status.value,
                failed_slot=failed_diag,
                max_states_hit=bool(
                    (diagnostics.beam_metrics or {}).get("max_states_hit")
                ),
            ).value

        if diagnostics.best_partial_score is None and meals:
            diagnostics.best_partial_score = float(score)
        if diagnostics.partial_plan is None:
            diagnostics.partial_plan = {
                "score": float(score),
                "assignments": [
                    {
                        "slot_id": m.slot_id,
                        "recipe_id": m.recipe_id,
                        "is_leftover": m.is_leftover,
                    }
                    for m in meals
                ],
            }

        if status in {PlanStatus.NO_PLAN, PlanStatus.PARTIAL}:
            logger.warning(
                "planner_failed status=%s termination=%s failed_slot=%s "
                "last_successful_slot=%s visited_states=%s beam_iterations=%s "
                "expanded=%s pruned=%s hard_filters=%s constraints=%s",
                status.value,
                diagnostics.termination_reason,
                diagnostics.failed_slot,
                diagnostics.last_successful_slot,
                diagnostics.visited_states,
                diagnostics.beam_iterations,
                diagnostics.states_expanded,
                diagnostics.states_pruned,
                diagnostics.hard_filter_stats,
                diagnostics.constraint_statistics,
            )

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
