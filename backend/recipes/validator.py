"""Deterministic Recipe Catalog validator (errors vs warnings)."""

from __future__ import annotations

from dataclasses import dataclass, field

from recipes.enums import CookingMethod, IngredientUnit, RecipeStatus, TagType, UsageTag
from recipes.schemas import RecipeCardSchema, RecipeRelationSchema


@dataclass
class ValidationIssue:
    code: str
    message: str
    path: str | None = None


@dataclass
class ValidationReport:
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def merge(self, other: ValidationReport) -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


class RecipeCatalogValidator:
    """Validates catalog payloads before import."""

    def validate_catalog(
        self,
        recipes: list[RecipeCardSchema],
        ingredient_ids: set[str],
        relations: list[RecipeRelationSchema],
    ) -> ValidationReport:
        report = ValidationReport()
        recipe_ids = [r.id for r in recipes]
        slugs = [r.slug for r in recipes]
        recipe_id_set = set(recipe_ids)

        if len(recipe_ids) != len(recipe_id_set):
            report.errors.append(
                ValidationIssue("DUPLICATE_RECIPE_ID", "Duplicate recipe id in catalog")
            )
        if len(slugs) != len(set(slugs)):
            report.errors.append(
                ValidationIssue("DUPLICATE_SLUG", "Duplicate recipe slug in catalog")
            )

        for recipe in recipes:
            report.merge(self.validate_recipe(recipe, ingredient_ids))

        for rel in relations:
            if rel.source_recipe_id == rel.target_recipe_id:
                report.errors.append(
                    ValidationIssue(
                        "SELF_RELATION",
                        "Relation source equals target",
                        path=rel.id,
                    )
                )
            if rel.source_recipe_id not in recipe_id_set:
                report.errors.append(
                    ValidationIssue(
                        "UNKNOWN_SOURCE_RECIPE",
                        f"Unknown source recipe {rel.source_recipe_id}",
                        path=rel.id,
                    )
                )
            if rel.target_recipe_id not in recipe_id_set:
                report.errors.append(
                    ValidationIssue(
                        "UNKNOWN_TARGET_RECIPE",
                        f"Unknown target recipe {rel.target_recipe_id}",
                        path=rel.id,
                    )
                )
            if not (0 <= rel.score <= 1):
                report.errors.append(
                    ValidationIssue("SCORE_OUT_OF_RANGE", "Relation score out of 0..1", path=rel.id)
                )

        recipes_with_relations = {
            r.source_recipe_id for r in relations
        } | {r.target_recipe_id for r in relations}
        for recipe in recipes:
            if recipe.id not in recipes_with_relations:
                report.warnings.append(
                    ValidationIssue(
                        "NO_RELATIONS",
                        "Recipe has no relations",
                        path=recipe.id,
                    )
                )

        return report

    def validate_recipe(
        self,
        recipe: RecipeCardSchema,
        ingredient_ids: set[str],
    ) -> ValidationReport:
        report = ValidationReport()
        path = recipe.id

        if not recipe.meal_types:
            report.errors.append(
                ValidationIssue("MISSING_MEAL_TYPE", "Recipe has no meal types", path=path)
            )
        if not recipe.ingredients:
            report.errors.append(
                ValidationIssue("MISSING_INGREDIENTS", "Recipe has no ingredients", path=path)
            )
        if not recipe.steps:
            report.errors.append(
                ValidationIssue("MISSING_STEPS", "Recipe has no steps", path=path)
            )

        for ing in recipe.ingredients:
            if ing.ingredient_id not in ingredient_ids:
                report.errors.append(
                    ValidationIssue(
                        "UNKNOWN_INGREDIENT",
                        f"Unknown ingredient_id {ing.ingredient_id}",
                        path=f"{path}/ingredients/{ing.sort_order}",
                    )
                )
            if ing.quantity <= 0:
                report.errors.append(
                    ValidationIssue(
                        "INVALID_QUANTITY",
                        "Ingredient quantity must be > 0",
                        path=f"{path}/ingredients/{ing.sort_order}",
                    )
                )
            try:
                IngredientUnit(ing.unit)
            except ValueError:
                report.errors.append(
                    ValidationIssue(
                        "UNKNOWN_UNIT",
                        f"Unknown unit {ing.unit}",
                        path=f"{path}/ingredients/{ing.sort_order}",
                    )
                )

        step_nums = sorted(s.step_number for s in recipe.steps)
        if step_nums and step_nums != list(range(1, len(step_nums) + 1)):
            report.errors.append(
                ValidationIssue("INVALID_STEP_SEQUENCE", "Steps must be contiguous from 1", path=path)
            )

        if recipe.base_servings <= 0:
            report.errors.append(
                ValidationIssue("INVALID_BASE_SERVINGS", "base_servings must be > 0", path=path)
            )
        if recipe.yield_weight_g <= 0:
            report.errors.append(
                ValidationIssue("INVALID_YIELD", "yield_weight_g must be > 0", path=path)
            )
        if recipe.recommended_portion_max_g < recipe.recommended_portion_min_g:
            report.errors.append(
                ValidationIssue("INVALID_PORTION_RANGE", "Invalid portion range", path=path)
            )
        if recipe.max_batch_servings < recipe.min_batch_servings:
            report.errors.append(
                ValidationIssue("INVALID_BATCH_RANGE", "Invalid batch range", path=path)
            )
        if not (
            recipe.min_batch_servings
            <= recipe.base_servings
            <= recipe.max_batch_servings
        ):
            report.errors.append(
                ValidationIssue(
                    "BASE_OUTSIDE_BATCH",
                    "base_servings outside batch range",
                    path=path,
                )
            )

        for role in recipe.roles:
            if not (0 <= role.score <= 1):
                report.errors.append(
                    ValidationIssue("SCORE_OUT_OF_RANGE", "Role score out of 0..1", path=path)
                )
        for goal in recipe.goal_scores:
            if not (0 <= goal.score <= 1):
                report.errors.append(
                    ValidationIssue("SCORE_OUT_OF_RANGE", "Goal score out of 0..1", path=path)
                )

        if recipe.status == RecipeStatus.ACTIVE and not recipe.cooking_methods:
            report.errors.append(
                ValidationIssue(
                    "ACTIVE_WITHOUT_METHOD",
                    "Active recipe requires cooking method",
                    path=path,
                )
            )

        for nutrient in (
            recipe.calories_per_100g,
            recipe.protein_g_per_100g,
            recipe.fat_g_per_100g,
            recipe.carbs_g_per_100g,
        ):
            if nutrient < 0:
                report.errors.append(
                    ValidationIssue("NEGATIVE_NUTRITION", "Negative nutrition value", path=path)
                )

        # Warnings
        if recipe.image_key is None:
            report.warnings.append(
                ValidationIssue("MISSING_IMAGE", "Recipe has no image_key", path=path)
            )

        if not recipe.goal_scores:
            report.warnings.append(
                ValidationIssue("MISSING_GOAL_SCORES", "Recipe has no goal scores", path=path)
            )

        if recipe.recommended_portion_min_g < 80 or recipe.recommended_portion_max_g > 600:
            report.warnings.append(
                ValidationIssue(
                    "SUSPICIOUS_PORTION",
                    "Recommended portion outside typical 80–600 g",
                    path=path,
                )
            )

        known_grams = [
            i.quantity_grams for i in recipe.ingredients if i.quantity_grams is not None
        ]
        if known_grams:
            total_g = sum(known_grams)
            if recipe.yield_weight_g > 0:
                ratio = total_g / recipe.yield_weight_g
                if ratio < 0.5 or ratio > 2.5:
                    report.warnings.append(
                        ValidationIssue(
                            "YIELD_MISMATCH",
                            "Ingredient grams differ strongly from yield_weight_g",
                            path=path,
                        )
                    )

        if recipe.protein_level.value == "high" and recipe.protein_g_per_100g < 8:
            report.warnings.append(
                ValidationIssue(
                    "LOW_PROTEIN_FOR_TAG",
                    "protein_level=high but protein_g_per_100g is low",
                    path=path,
                )
            )

        if recipe.batch_friendly and recipe.max_batch_servings < 4:
            report.warnings.append(
                ValidationIssue(
                    "BATCH_MAX_LOW",
                    "batch_friendly but max_batch_servings < 4",
                    path=path,
                )
            )

        if recipe.leftover_friendly and (
            recipe.storage_days is None or recipe.storage_days < 1
        ):
            report.warnings.append(
                ValidationIssue(
                    "LEFTOVER_WITHOUT_STORAGE",
                    "leftover_friendly without storage_days >= 1",
                    path=path,
                )
            )

        usage_quick = any(
            t.tag_type == TagType.USAGE and t.tag_value == UsageTag.QUICK.value
            for t in recipe.tags
        )
        if usage_quick and recipe.total_time_minutes > 30:
            report.warnings.append(
                ValidationIssue(
                    "QUICK_BUT_SLOW",
                    "usage=quick but total_time_minutes > 30",
                    path=path,
                )
            )

        if len(recipe.ingredients) > 20:
            report.warnings.append(
                ValidationIssue(
                    "MANY_INGREDIENTS",
                    "Suspiciously many ingredients",
                    path=path,
                )
            )

        for step in recipe.steps:
            if not step.ingredient_refs:
                report.warnings.append(
                    ValidationIssue(
                        "STEP_UNLINKED",
                        f"Step {step.step_number} not linked to ingredients",
                        path=path,
                    )
                )

        if (
            recipe.requires_cooking
            and CookingMethod.NO_COOK in recipe.cooking_methods
            and len(recipe.cooking_methods) == 1
        ):
            report.warnings.append(
                ValidationIssue(
                    "REQUIRES_COOKING_NO_COOK",
                    "requires_cooking with only no_cook method",
                    path=path,
                )
            )

        if recipe.status == RecipeStatus.ACTIVE and report.errors:
            report.errors.append(
                ValidationIssue(
                    "ACTIVE_WITH_ERRORS",
                    "Cannot import active recipe with validation errors",
                    path=path,
                )
            )

        return report
