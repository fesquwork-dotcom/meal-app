"""Deterministic soft scorer — active components only in the denominator."""

from __future__ import annotations

from recipes.enums import BudgetClass, RecipeRole, TagType, UsageTag
from recipes.models import Recipe
from recipes.selection.codes import SoftReasonCode
from recipes.selection.context import CandidateSelectionContext
from recipes.selection.models import RecipeScoreBreakdown
from recipes.selection.weights import (
    BUDGET_CLASS_RANK,
    DEFAULT_SCORING_WEIGHTS,
    RecipeScoringWeights,
)

GOAL_NEUTRAL = 0.5
TIME_SCORE_FLOOR = 0.35


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


class RecipeScorer:
    def __init__(self, weights: RecipeScoringWeights | None = None) -> None:
        self.weights = weights or DEFAULT_SCORING_WEIGHTS

    def score(
        self,
        recipe: Recipe,
        context: CandidateSelectionContext,
    ) -> tuple[float, RecipeScoreBreakdown, list[str], list[str]]:
        """Returns (score, breakdown, reason_codes, matched_preferences)."""
        components: dict[str, float] = {}
        active_weights: dict[str, float] = {}
        reasons: list[str] = []
        matched: list[str] = []
        w = self.weights

        # --- goal ---
        if context.goal is not None:
            goal_map = {g.goal: g.score for g in recipe.goal_scores}
            if context.goal in goal_map:
                gscore = float(goal_map[context.goal])
            else:
                gscore = GOAL_NEUTRAL
            components["goal"] = gscore
            active_weights["goal"] = w.goal
            if gscore >= 0.7:
                reasons.append(SoftReasonCode.GOAL_MATCH.value)
                matched.append(f"goal:{context.goal.value}")
            elif gscore < 0.45:
                reasons.append(SoftReasonCode.LOW_GOAL_SCORE.value)

        # --- budget (within allowed set) ---
        if context.allowed_budget_classes is not None and context.allowed_budget_classes:
            components["budget"] = self._budget_score(
                recipe.budget_class, context.allowed_budget_classes
            )
            active_weights["budget"] = w.budget
            if recipe.budget_class in {
                BudgetClass.VERY_BUDGET,
                BudgetClass.BUDGET,
            } and components["budget"] >= 0.5:
                reasons.append(SoftReasonCode.BUDGET_FRIENDLY.value)

        # --- time ---
        if context.max_total_time_minutes is not None:
            components["time"] = self._time_score(
                recipe.total_time_minutes, context.max_total_time_minutes
            )
            active_weights["time"] = w.time
            if recipe.total_time_minutes <= max(
                15, int(context.max_total_time_minutes * 0.6)
            ):
                reasons.append(SoftReasonCode.QUICK_PREPARATION.value)

        # --- preferred ingredients ---
        if context.preferred_ingredient_ids:
            components["preferred_ingredients"] = self._preferred_ingredient_score(
                recipe, context.preferred_ingredient_ids
            )
            active_weights["preferred_ingredients"] = w.preferred_ingredients
            if components["preferred_ingredients"] > 0:
                reasons.append(SoftReasonCode.PREFERRED_INGREDIENT_MATCH.value)
                matched.append("preferred_ingredients")

        # --- preferred tags ---
        if context.preferred_tags:
            components["preferred_tags"] = self._preferred_tag_score(
                recipe, context.preferred_tags
            )
            active_weights["preferred_tags"] = w.preferred_tags
            if components["preferred_tags"] > 0:
                reasons.append(SoftReasonCode.PREFERRED_TAG_MATCH.value)
                matched.append("preferred_tags")

        # --- protein source ---
        if context.preferred_protein_sources:
            components["protein_source"] = self._protein_score(
                recipe, context.preferred_protein_sources
            )
            active_weights["protein_source"] = w.protein_source
            if components["protein_source"] >= 1.0:
                reasons.append(SoftReasonCode.PREFERRED_PROTEIN_SOURCE.value)
                matched.append("preferred_protein_source")

        # --- roles ---
        if context.desired_roles:
            components["role"] = self._role_score(recipe, context.desired_roles)
            active_weights["role"] = w.role
            if components["role"] >= 0.7:
                reasons.append(SoftReasonCode.ROLE_MATCH.value)
                matched.append("desired_role")
            elif components["role"] == 0.0:
                reasons.append(SoftReasonCode.LOW_ROLE_SCORE.value)

        # --- batch ---
        if context.prefer_batch_friendly:
            components["batch"] = 1.0 if recipe.batch_friendly else 0.2
            active_weights["batch"] = w.batch
            if recipe.batch_friendly:
                reasons.append(SoftReasonCode.BATCH_FRIENDLY.value)
                matched.append("batch_friendly")

        # --- leftover ---
        if context.allow_leftovers:
            components["leftover"] = 1.0 if recipe.leftover_friendly else 0.35
            active_weights["leftover"] = w.leftover
            if recipe.leftover_friendly:
                reasons.append(SoftReasonCode.LEFTOVER_FRIENDLY.value)
                matched.append("leftover_friendly")

        # --- family ---
        if context.family_mode:
            components["family"] = self._family_score(recipe)
            active_weights["family"] = w.family
            if components["family"] >= 0.6:
                reasons.append(SoftReasonCode.FAMILY_FRIENDLY.value)
                matched.append("family")

        if not active_weights:
            # No soft criteria — neutral ranking by name/id only.
            final = 0.5
            penalty = 0.0
        else:
            weighted_sum = sum(
                components[name] * weight for name, weight in active_weights.items()
            )
            weight_sum = sum(active_weights.values())
            final = weighted_sum / weight_sum if weight_sum > 0 else 0.5
            penalty = self._diversity_penalty(recipe, context)
            if penalty:
                reasons.append(SoftReasonCode.REPEATED_INGREDIENT_PENALTY.value)
            final = _clamp01(final + penalty)

        # Deduplicate reasons preserving order
        seen: set[str] = set()
        unique_reasons: list[str] = []
        for code in reasons:
            if code not in seen:
                seen.add(code)
                unique_reasons.append(code)

        breakdown = RecipeScoreBreakdown(
            components=components,
            diversity_penalty=penalty if active_weights else 0.0,
            active_weights=active_weights,
        )
        return final, breakdown, unique_reasons, matched

    @staticmethod
    def _budget_score(
        budget_class: BudgetClass,
        allowed: list[BudgetClass],
    ) -> float:
        ranks = [BUDGET_CLASS_RANK[b.value] for b in allowed]
        if not ranks:
            return 0.5
        min_rank = min(ranks)
        max_rank = max(ranks)
        recipe_rank = BUDGET_CLASS_RANK[budget_class.value]
        if max_rank == min_rank:
            return 1.0
        # Lower rank (more budget) → higher score; keep a floor for allowed classes.
        raw = 1.0 - (recipe_rank - min_rank) / (max_rank - min_rank)
        return _clamp01(0.25 + 0.75 * raw)

    @staticmethod
    def _time_score(recipe_time: int, max_time: int) -> float:
        if max_time <= 0:
            return 0.5
        raw = 1.0 - (recipe_time / max_time)
        return _clamp01(max(TIME_SCORE_FLOOR, raw))

    @staticmethod
    def _preferred_ingredient_score(
        recipe: Recipe,
        preferred: set[str],
    ) -> float:
        recipe_ids = {i.ingredient_id for i in recipe.ingredients}
        hits = len(recipe_ids & preferred)
        if not preferred:
            return 0.0
        # Cap so many hits do not dominate.
        return _clamp01(hits / len(preferred))

    @staticmethod
    def _preferred_tag_score(
        recipe: Recipe,
        preferred: set[tuple[str, str]],
    ) -> float:
        recipe_pairs = {(t.tag_type.value, t.tag_value) for t in recipe.tags}
        hits = len(recipe_pairs & preferred)
        if not preferred:
            return 0.0
        return _clamp01(min(1.0, hits / max(1, min(3, len(preferred)))))

    @staticmethod
    def _protein_score(recipe: Recipe, preferred: set) -> float:
        protein_tags = {
            t.tag_value
            for t in recipe.tags
            if t.tag_type == TagType.PROTEIN_SOURCE
        }
        preferred_vals = {p.value if hasattr(p, "value") else str(p) for p in preferred}
        if protein_tags & preferred_vals:
            return 1.0
        return 0.0

    @staticmethod
    def _role_score(recipe: Recipe, desired: list[RecipeRole]) -> float:
        role_map = {r.role: r.score for r in recipe.roles}
        best = 0.0
        for role in desired:
            if role in role_map:
                best = max(best, float(role_map[role]))
        return _clamp01(best)

    @staticmethod
    def _family_score(recipe: Recipe) -> float:
        score = 0.0
        for role in recipe.roles:
            if role.role == RecipeRole.FAMILY_MEAL:
                score = max(score, float(role.score))
        has_family_tag = any(
            t.tag_type == TagType.USAGE and t.tag_value == UsageTag.FAMILY.value
            for t in recipe.tags
        )
        if has_family_tag:
            score = max(score, 0.75)
        return _clamp01(score)

    def _diversity_penalty(
        self,
        recipe: Recipe,
        context: CandidateSelectionContext,
    ) -> float:
        if not context.avoid_ingredient_ids:
            return 0.0
        recipe_ids = {
            i.ingredient_id for i in recipe.ingredients if not i.is_optional
        }
        hits = len(recipe_ids & context.avoid_ingredient_ids)
        if hits == 0:
            return 0.0
        # Soft penalty: more hits → stronger, capped.
        strength = self.weights.diversity_penalty_strength
        return -_clamp01(hits / max(1, len(context.avoid_ingredient_ids))) * strength
