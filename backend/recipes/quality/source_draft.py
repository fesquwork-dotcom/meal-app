"""Build SourceBackedRecipeDraft from concept + observations."""

from __future__ import annotations

from recipes.quality.source_comparison import RecipeSourceComparison, normalize_ingredient_name
from recipes.quality.source_models import (
    NormalizedIngredient,
    RecipeConcept,
    RecipeSourceObservation,
    SourceBackedRecipeDraft,
)


class SourceBackedDraftBuilder:
    """Produce a draft and decide ready_for_catalog_import."""

    def __init__(self, comparison: RecipeSourceComparison | None = None) -> None:
        self.comparison = comparison or RecipeSourceComparison()

    def build(
        self,
        concept: RecipeConcept,
        observations: list[RecipeSourceObservation],
        *,
        ingredient_id_map: dict[str, str] | None = None,
    ) -> SourceBackedRecipeDraft:
        cmp = self.comparison.compare(concept, observations)
        ingredient_id_map = ingredient_id_map or {}

        normalized: list[NormalizedIngredient] = []
        for name in cmp.ingredient_consensus:
            rng = cmp.proportion_ranges.get(name) or {}
            qty = rng.get("mid")
            normalized.append(
                NormalizedIngredient(
                    ingredient_id=ingredient_id_map.get(name),
                    name=name,
                    quantity=qty,
                    unit="g" if qty is not None else None,
                    quantity_grams=qty,
                )
            )

        # Prefer mid of observed times; fall back to concept max
        total = cmp.recommended_normalization.get("total_time_minutes")
        cook_vals = [
            o.cook_time_minutes for o in observations if o.cook_time_minutes is not None
        ]
        prep_vals = [
            o.prep_time_minutes for o in observations if o.prep_time_minutes is not None
        ]
        cook = int(round(sum(cook_vals) / len(cook_vals))) if cook_vals else None
        prep = int(round(sum(prep_vals) / len(prep_vals))) if prep_vals else None

        yield_servings = cmp.recommended_normalization.get("yield_servings")
        notes = [
            f"Compared {len(observations)} sources for concept {concept.concept_id}",
        ]
        if cmp.disagreement_fields:
            notes.append(
                "Disagreements: " + ", ".join(sorted(set(cmp.disagreement_fields)))
            )

        draft = SourceBackedRecipeDraft(
            concept=concept,
            source_ids=[o.source_id for o in observations],
            observations=observations,
            comparison=cmp,
            normalized_ingredients=normalized,
            normalized_method=cmp.cooking_method_consensus,
            normalized_prep_time_minutes=prep,
            normalized_cook_time_minutes=cook,
            normalized_total_time_minutes=int(total) if total is not None else None,
            normalized_yield_servings=float(yield_servings)
            if yield_servings is not None
            else None,
            normalization_notes=notes,
            unresolved_questions=list(cmp.unresolved_questions),
            confidence=cmp.confidence,
        )
        draft.blocking_reasons = self._blocking_reasons(draft)
        draft.ready_for_catalog_import = len(draft.blocking_reasons) == 0
        return draft

    def _blocking_reasons(self, draft: SourceBackedRecipeDraft) -> list[str]:
        reasons: list[str] = []
        if len(draft.observations) < 2:
            reasons.append("source_count_lt_2")
        if draft.comparison and draft.comparison.critical_contradiction:
            reasons.append("critical_source_contradiction")
        if not draft.normalized_ingredients:
            reasons.append("main_ingredients_unconfirmed")
        if not draft.normalized_method:
            reasons.append("cooking_method_unconfirmed")
        if draft.normalized_total_time_minutes is None and not any(
            o.cook_time_minutes is not None or o.total_time_minutes is not None
            for o in draft.observations
        ):
            reasons.append("time_unconfirmed")
        # Blocking unresolved questions (prefixed)
        for q in draft.unresolved_questions:
            if q.startswith("critical_") or q.startswith("need_at_least_"):
                reasons.append(q)
            if q in {
                "empty_or_placeholder_reference",
                "llm_cannot_be_source",
                "duplicate_source_reference",
                "no_ingredient_consensus",
                "primary_protein_not_in_consensus",
            } or q.startswith("primary_protein_not_in_consensus"):
                if q not in reasons:
                    reasons.append(q)
        # Deduplicate
        seen: set[str] = set()
        unique: list[str] = []
        for r in reasons:
            if r in seen:
                continue
            seen.add(r)
            unique.append(r)
        return unique


def observation_names(observations: list[RecipeSourceObservation]) -> set[str]:
    names: set[str] = set()
    for obs in observations:
        for ing in obs.ingredients:
            names.add(normalize_ingredient_name(ing.name))
    return names
