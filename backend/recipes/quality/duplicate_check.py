"""Duplicate concept protection against existing catalog recipes."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from recipes.models import Recipe
from recipes.quality.source_comparison import normalize_ingredient_name
from recipes.quality.source_models import RecipeConcept, SourceBackedRecipeDraft


@dataclass
class DuplicateCheckResult:
    is_duplicate: bool
    matched_recipe_id: str | None = None
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RecipeDuplicateChecker:
    """Heuristic near-duplicate detector for new concepts/drafts."""

    DUPLICATE_THRESHOLD = 0.78

    def check(
        self,
        *,
        concept: RecipeConcept,
        existing: Iterable[Recipe],
        draft: SourceBackedRecipeDraft | None = None,
        proposed_ingredient_ids: set[str] | None = None,
        proposed_method: str | None = None,
        proposed_total_time: int | None = None,
        proposed_meal_types: set[str] | None = None,
    ) -> DuplicateCheckResult:
        proposed_ings = set(proposed_ingredient_ids or set())
        if draft is not None:
            for ing in draft.normalized_ingredients:
                if ing.ingredient_id:
                    proposed_ings.add(ing.ingredient_id)
                proposed_ings.add(f"ing_{normalize_ingredient_name(ing.name)}")
            proposed_method = proposed_method or draft.normalized_method
            proposed_total_time = (
                proposed_total_time
                if proposed_total_time is not None
                else draft.normalized_total_time_minutes
            )
        meal_types = proposed_meal_types or set(concept.target_meal_types)
        protein = (concept.primary_protein or "").lower()

        best: DuplicateCheckResult = DuplicateCheckResult(is_duplicate=False)
        for recipe in existing:
            score = 0.0
            reasons: list[str] = []

            recipe_ings = {i.ingredient_id for i in recipe.ingredients}
            if proposed_ings and recipe_ings:
                inter = proposed_ings & recipe_ings
                union = proposed_ings | recipe_ings
                jaccard = len(inter) / max(len(union), 1)
                score += 0.35 * jaccard
                if jaccard >= 0.7:
                    reasons.append(f"ingredient_overlap={jaccard:.2f}")

            recipe_meals = {m.meal_type.value for m in recipe.meal_types} | {
                recipe.primary_meal_type.value
            }
            if meal_types & recipe_meals:
                score += 0.15
                reasons.append("meal_type_overlap")

            # Protein tag overlap
            recipe_proteins = {
                t.tag_value
                for t in recipe.tags
                if t.tag_type.value == "protein_source"
            }
            if protein and protein in recipe_proteins:
                score += 0.2
                reasons.append("same_primary_protein")

            methods = {m.value for m in recipe.cooking_methods}
            if proposed_method:
                pm = proposed_method.lower()
                if any(pm in m or m in pm for m in methods):
                    score += 0.15
                    reasons.append("same_method_family")

            if proposed_total_time is not None:
                delta = abs(recipe.total_time_minutes - proposed_total_time)
                if delta <= 10:
                    score += 0.1
                    reasons.append("similar_time")

            # Title / concept similarity (rough)
            title_blob = f"{recipe.name} {recipe.slug}".lower()
            concept_blob = f"{concept.title} {concept.concept_id}".lower()
            shared_tokens = set(title_blob.split()) & set(concept_blob.replace("-", " ").split())
            stop = {"with", "and", "the", "a", "recipe", "001", "lunch", "dinner", "breakfast"}
            shared_tokens -= stop
            if len(shared_tokens) >= 2:
                score += 0.15
                reasons.append(f"title_tokens={sorted(shared_tokens)}")

            if score > best.score:
                best = DuplicateCheckResult(
                    is_duplicate=score >= self.DUPLICATE_THRESHOLD,
                    matched_recipe_id=recipe.id,
                    score=round(score, 3),
                    reasons=reasons,
                )
        return best
