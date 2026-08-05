"""Weekly plan scoring (uses Selector score as one input; does not change Selector)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from recipes.enums import MealType
from recipes.models import Recipe
from recipes.planning.candidate_provider import primary_protein, recipe_ingredient_ids
from recipes.planning.codes import PlannerReasonCode
from recipes.planning.context import WeeklyPlanningContext
from recipes.planning.models import ScoreBreakdown
from recipes.planning.relations import RelationIndex
from recipes.planning.slots import WeeklyMealSlot
from recipes.planning.weights import WeeklyPlannerWeights


@dataclass
class AssignmentView:
    slot: WeeklyMealSlot
    recipe: Recipe
    selector_score: float
    is_leftover: bool
    cook_day_miss: bool = False


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class WeeklyPlanScorer:
    def __init__(self, weights: WeeklyPlannerWeights | None = None) -> None:
        self.weights = weights

    def score_plan(
        self,
        *,
        assignments: list[AssignmentView],
        context: WeeklyPlanningContext,
        relation_index: RelationIndex,
    ) -> tuple[float, ScoreBreakdown, dict[str, list[str]]]:
        w = self.weights or context.weights
        if not assignments:
            return 0.0, ScoreBreakdown(), {}

        reasons: dict[str, list[str]] = {a.slot.slot_id: [] for a in assignments}

        selector_quality = sum(a.selector_score for a in assignments) / len(assignments)
        for a in assignments:
            reasons[a.slot.slot_id].append(PlannerReasonCode.SELECTOR_QUALITY.value)

        cooked_ids = [a.recipe.id for a in assignments if not a.is_leftover]
        unique_ratio = len(set(cooked_ids)) / max(1, len(cooked_ids))
        recipe_diversity = unique_ratio
        for a in assignments:
            if not a.is_leftover:
                reasons[a.slot.slot_id].append(PlannerReasonCode.RECIPE_DIVERSITY.value)

        proteins = [
            primary_protein(a.recipe)
            for a in assignments
            if a.slot.meal_type != MealType.BREAKFAST
        ]
        proteins = [p for p in proteins if p]
        if proteins:
            protein_diversity = len(set(proteins)) / len(proteins)
        else:
            protein_diversity = 1.0

        consec_pen = 0.0
        for i in range(1, len(assignments)):
            prev, cur = assignments[i - 1], assignments[i]
            if prev.slot.meal_type == MealType.BREAKFAST or cur.slot.meal_type == MealType.BREAKFAST:
                scale = w.breakfast_diversity_scale
            else:
                scale = 1.0
            p1, p2 = primary_protein(prev.recipe), primary_protein(cur.recipe)
            if p1 and p2 and p1 == p2 and prev.slot.day_index == cur.slot.day_index:
                consec_pen += w.consecutive_protein_penalty * scale
            if p1 and p2 and p1 == p2 and cur.slot.day_index == prev.slot.day_index + 1:
                if {prev.slot.meal_type, cur.slot.meal_type} <= {
                    MealType.LUNCH,
                    MealType.DINNER,
                }:
                    consec_pen += w.consecutive_protein_penalty * 0.5 * scale

        protein_diversity = _clamp01(protein_diversity - consec_pen)
        for a in assignments:
            if a.slot.meal_type != MealType.BREAKFAST:
                reasons[a.slot.slot_id].append(PlannerReasonCode.PROTEIN_DIVERSITY.value)

        relation_hits = 0.0
        relation_total = 0.0
        similar_pen = 0.0
        for i, a in enumerate(assignments):
            for j, b in enumerate(assignments):
                if j >= i:
                    continue
                if abs(a.slot.day_index - b.slot.day_index) > 1:
                    continue
                relation_total += 1
                if relation_index.has_good_pair(a.recipe.id, b.recipe.id):
                    relation_hits += 1.0
                    reasons[a.slot.slot_id].append(PlannerReasonCode.GOOD_PAIR.value)
                if relation_index.has_shares(a.recipe.id, b.recipe.id):
                    relation_hits += 0.5
                    reasons[a.slot.slot_id].append(
                        PlannerReasonCode.SHARES_INGREDIENTS.value
                    )
                if relation_index.has_similar(a.recipe.id, b.recipe.id):
                    scale = (
                        w.breakfast_diversity_scale
                        if MealType.BREAKFAST
                        in {a.slot.meal_type, b.slot.meal_type}
                        else 1.0
                    )
                    similar_pen += w.similar_meal_penalty * scale
                    reasons[a.slot.slot_id].append(
                        PlannerReasonCode.AVOIDED_SIMILAR_MEAL.value
                    )
        relation_score = _clamp01(
            (relation_hits / relation_total if relation_total else 0.5) - similar_pen
        )

        cook_matches = sum(
            1
            for a in assignments
            if (not a.is_leftover and a.slot.is_cook_day) or a.is_leftover
        )
        strategy_alignment = cook_matches / len(assignments)
        for a in assignments:
            if a.is_leftover:
                reasons[a.slot.slot_id].append(PlannerReasonCode.LEFTOVER_REUSE.value)
            elif a.cook_day_miss:
                reasons[a.slot.slot_id].append(PlannerReasonCode.COOK_DAY_MISS.value)
            elif a.slot.is_cook_day and not a.is_leftover:
                reasons[a.slot.slot_id].append(PlannerReasonCode.COOK_DAY_MATCH.value)
            reasons[a.slot.slot_id].append(PlannerReasonCode.STRATEGY_ALIGNMENT.value)

        leftovers = sum(1 for a in assignments if a.is_leftover)
        batch_cooks = sum(
            1
            for a in assignments
            if not a.is_leftover and a.recipe.batch_friendly and a.recipe.leftover_friendly
        )
        if context.leftovers_enabled:
            batch_efficiency = _clamp01(
                (leftovers + 0.5 * batch_cooks) / max(1, context.days)
            )
            for a in assignments:
                if not a.is_leftover and a.recipe.batch_friendly:
                    reasons[a.slot.slot_id].append(PlannerReasonCode.BATCH_FRIENDLY.value)
        else:
            batch_efficiency = 1.0 if leftovers == 0 else 0.0

        # Bounded ingredient reuse
        ing_counter: Counter[str] = Counter()
        for a in assignments:
            ing_counter.update(recipe_ingredient_ids(a.recipe))
        reused = sum(1 for _ing, cnt in ing_counter.items() if cnt >= 2)
        total_ings = max(1, len(ing_counter))
        raw_reuse = reused / total_ings
        ingredient_reuse = min(raw_reuse, w.ingredient_reuse_cap)
        if ingredient_reuse > 0.05:
            for a in assignments:
                reasons[a.slot.slot_id].append(PlannerReasonCode.INGREDIENT_REUSE.value)

        # Independent cook repeats beyond 1
        cook_counts = Counter(cooked_ids)
        excess_repeats = sum(max(0, c - 1) for c in cook_counts.values())
        repeat_penalty = min(1.0, excess_repeats * w.recipe_repeat_penalty)
        # Strong penalty from config when set (relaxation pass); else weight default.
        miss_unit = (
            float(context.config.extra_cook_day_penalty)
            if context.config.extra_cook_day_penalty is not None
            else w.cook_day_miss_penalty
        )
        cook_miss_pen = sum(miss_unit for a in assignments if a.cook_day_miss)

        weighted = (
            w.selector_quality * selector_quality
            + w.recipe_diversity * recipe_diversity
            + w.protein_diversity * protein_diversity
            + w.relation_score * relation_score
            + w.strategy_alignment * strategy_alignment
            + w.batch_efficiency * batch_efficiency
            + w.ingredient_reuse * ingredient_reuse
        )
        total_w = (
            w.selector_quality
            + w.recipe_diversity
            + w.protein_diversity
            + w.relation_score
            + w.strategy_alignment
            + w.batch_efficiency
            + w.ingredient_reuse
        )
        score = _clamp01(weighted / total_w - repeat_penalty - cook_miss_pen)

        breakdown = ScoreBreakdown(
            selector_quality=selector_quality,
            recipe_diversity=recipe_diversity,
            protein_diversity=protein_diversity,
            relation_score=relation_score,
            strategy_alignment=strategy_alignment,
            batch_efficiency=batch_efficiency,
            ingredient_reuse=ingredient_reuse,
            repeat_penalty=repeat_penalty + cook_miss_pen,
        )

        # Deduplicate reasons per slot while preserving order
        for slot_id, codes in reasons.items():
            seen: set[str] = set()
            ordered: list[str] = []
            for code in codes:
                if code not in seen:
                    seen.add(code)
                    ordered.append(code)
            reasons[slot_id] = ordered

        return score, breakdown, reasons

    def incremental_key(
        self,
        *,
        assignments: list[AssignmentView],
        context: WeeklyPlanningContext,
        relation_index: RelationIndex,
        next_candidate_id: str,
    ) -> tuple:
        """Deterministic sort key for beam: higher score first, then recipe ids."""
        score, _, _ = self.score_plan(
            assignments=assignments,
            context=context,
            relation_index=relation_index,
        )
        ids = tuple(a.recipe.id for a in assignments)
        return (-score, ids, next_candidate_id)
