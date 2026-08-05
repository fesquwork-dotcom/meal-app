"""Source review for existing catalog recipes (no auto-mutation)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from recipes.models import Recipe
from recipes.quality.enums import MetadataRecommendationType
from recipes.quality.models import MetadataRecommendation
from recipes.quality.source_comparison import (
    RecipeSourceComparison,
    normalize_ingredient_name,
)
from recipes.quality.source_models import (
    RecipeConcept,
    RecipeSourceComparisonResult,
    RecipeSourceObservation,
)


@dataclass
class SourceReviewResult:
    recipe_id: str
    source_count: int
    comparison: RecipeSourceComparisonResult
    mismatches: list[MetadataRecommendation] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    passed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "recipe_id": self.recipe_id,
            "source_count": self.source_count,
            "comparison": self.comparison.to_dict(),
            "mismatches": [m.to_dict() for m in self.mismatches],
            "notes": list(self.notes),
            "passed": self.passed,
        }


class RecipeSourceReviewer:
    """Compare catalog recipe facts to source observations without rewriting."""

    TIME_MISMATCH_RATIO = 0.35
    PROPORTION_MISMATCH_RATIO = 0.5

    def __init__(self, comparison: RecipeSourceComparison | None = None) -> None:
        self.comparison = comparison or RecipeSourceComparison()

    def review(
        self,
        recipe: Recipe,
        observations: list[RecipeSourceObservation],
        *,
        concept: RecipeConcept | None = None,
    ) -> SourceReviewResult:
        concept = concept or RecipeConcept(
            concept_id=recipe.id,
            title=recipe.name,
            target_meal_types=[recipe.primary_meal_type.value],
        )
        cmp = self.comparison.compare(concept, observations)
        mismatches: list[MetadataRecommendation] = []
        notes: list[str] = []

        # Ingredient presence vs consensus
        recipe_ings = {
            normalize_ingredient_name(i.ingredient_id.replace("ing_", ""))
            for i in recipe.ingredients
        }
        # Also try raw ingredient_id tails
        recipe_ings |= {i.ingredient_id.replace("ing_", "") for i in recipe.ingredients}

        for name in cmp.ingredient_consensus:
            if name not in recipe_ings and not any(
                name in rid or rid in name for rid in recipe_ings
            ):
                mismatches.append(
                    self._mismatch(
                        recipe.id,
                        field=f"ingredients.{name}",
                        current_value="absent",
                        derived_value="present_in_sources",
                        details={"ingredient": name},
                        message=f"Source consensus includes {name} missing from recipe",
                    )
                )

        # Time
        if cmp.time_range.get("recommended_total") is not None:
            recommended = int(cmp.time_range["recommended_total"])
            current = recipe.total_time_minutes
            mid = max(recommended, 1)
            if abs(current - recommended) / mid > self.TIME_MISMATCH_RATIO:
                mismatches.append(
                    self._mismatch(
                        recipe.id,
                        field="total_time_minutes",
                        current_value=current,
                        derived_value=recommended,
                        details={
                            "time_range": cmp.time_range,
                            "recipe_total": current,
                        },
                        message="Recipe total time diverges from source consensus",
                    )
                )
                notes.append(
                    f"time_mismatch recipe={current} sources≈{recommended}"
                )

        # Method family
        recipe_methods = {m.value for m in recipe.cooking_methods}
        consensus = (cmp.cooking_method_consensus or "").lower()
        if consensus:
            method_ok = any(
                key in consensus
                for key in recipe_methods
            ) or any(
                rm in consensus or consensus in rm for rm in recipe_methods
            )
            # Map frying/saute etc.
            fry_keys = {"frying", "sauteing", "stir_frying", "pan_frying"}
            boil_keys = {"boiling", "simmering"}
            if "stir" in consensus or "fry" in consensus or "saute" in consensus:
                method_ok = method_ok or bool(recipe_methods & fry_keys) or "frying" in recipe_methods
            if "boil" in consensus or "simmer" in consensus or "porridge" in consensus:
                method_ok = method_ok or bool(recipe_methods & boil_keys) or "boiling" in recipe_methods
            if "bake" in consensus or "roast" in consensus:
                method_ok = method_ok or "baking" in recipe_methods or "roasting" in recipe_methods
            if not method_ok:
                mismatches.append(
                    self._mismatch(
                        recipe.id,
                        field="cooking_methods",
                        current_value=sorted(recipe_methods),
                        derived_value=consensus,
                        details={},
                        message="Cooking method diverges from source consensus",
                    )
                )

        # Yield servings rough check
        if cmp.yield_range.get("recommended_servings") is not None:
            recommended_y = float(cmp.yield_range["recommended_servings"])
            current_y = float(recipe.base_servings)
            mid = max(recommended_y, 1)
            if abs(current_y - recommended_y) / mid > 0.6:
                mismatches.append(
                    self._mismatch(
                        recipe.id,
                        field="base_servings",
                        current_value=current_y,
                        derived_value=recommended_y,
                        details={"yield_range": cmp.yield_range},
                        message="Servings diverge from source consensus",
                    )
                )

        passed = (
            len(observations) >= 2
            and not cmp.critical_contradiction
            and not any(
                e in cmp.unresolved_questions
                for e in (
                    "empty_or_placeholder_reference",
                    "llm_cannot_be_source",
                    "duplicate_source_reference",
                )
            )
            and not any(q.startswith("need_at_least_") for q in cmp.unresolved_questions)
        )
        # Soft mismatches do not fail source review — they create recommendations
        return SourceReviewResult(
            recipe_id=recipe.id,
            source_count=len(observations),
            comparison=cmp,
            mismatches=mismatches,
            notes=notes,
            passed=passed,
        )

    @staticmethod
    def _mismatch(
        recipe_id: str,
        *,
        field: str,
        current_value: Any,
        derived_value: Any,
        details: dict[str, Any],
        message: str,
    ) -> MetadataRecommendation:
        return MetadataRecommendation(
            recipe_id=recipe_id,
            recommendation_type=MetadataRecommendationType.RECIPE_SOURCE_MISMATCH,
            field=field,
            current_value=current_value,
            derived_value=derived_value,
            evidence=details,
            severity="warning",
            reason_code="RECIPE_SOURCE_MISMATCH",
            message=message,
        )
