"""Recipe nutrition snapshot sanity + ingredient-level calculation stubs."""

from __future__ import annotations

from typing import Any

import aiosqlite

from recipes.models import Recipe
from recipes.quality.config import DEFAULT_QUALITY_THRESHOLDS, QualityThresholds
from recipes.quality.models import CheckSummary, QualityIssue


class RecipeNutritionCalculator:
    """Does not invent ingredient nutrition values."""

    def __init__(self, thresholds: QualityThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_QUALITY_THRESHOLDS

    def check_snapshot(self, recipe: Recipe) -> CheckSummary:
        issues: list[QualityIssue] = []
        metrics: dict[str, Any] = {
            "calories_per_100g": recipe.calories_per_100g,
            "protein_g_per_100g": recipe.protein_g_per_100g,
            "fat_g_per_100g": recipe.fat_g_per_100g,
            "carbs_g_per_100g": recipe.carbs_g_per_100g,
        }

        for name, value in (
            ("calories_per_100g", recipe.calories_per_100g),
            ("protein_g_per_100g", recipe.protein_g_per_100g),
            ("fat_g_per_100g", recipe.fat_g_per_100g),
            ("carbs_g_per_100g", recipe.carbs_g_per_100g),
        ):
            if value < 0:
                issues.append(
                    QualityIssue(
                        code="NUTRITION_NEGATIVE_VALUE",
                        message=f"{name} is negative",
                        severity="error",
                        path=name,
                        details={"value": value},
                    )
                )

        estimated = (
            recipe.protein_g_per_100g * 4
            + recipe.carbs_g_per_100g * 4
            + recipe.fat_g_per_100g * 9
        )
        metrics["estimated_kcal_from_macros"] = round(estimated, 2)
        abs_tol = self.thresholds.nutrition_kcal_absolute_tolerance
        rel_tol = self.thresholds.nutrition_kcal_relative_tolerance
        allowed = max(abs_tol, recipe.calories_per_100g * rel_tol)
        metrics["kcal_tolerance"] = round(allowed, 2)
        delta = abs(estimated - recipe.calories_per_100g)
        metrics["kcal_delta"] = round(delta, 2)
        if delta > allowed:
            issues.append(
                QualityIssue(
                    code="NUTRITION_MACRO_KCAL_MISMATCH",
                    message=(
                        f"Macro-estimated kcal {estimated:.1f} differs from "
                        f"snapshot {recipe.calories_per_100g:.1f} "
                        f"(tolerance {allowed:.1f})"
                    ),
                    severity="warning",
                    path="calories_per_100g",
                    details={
                        "estimated": estimated,
                        "snapshot": recipe.calories_per_100g,
                        "tolerance": allowed,
                    },
                )
            )

        if recipe.protein_g_per_100g > self.thresholds.suspicious_protein_g_per_100g:
            issues.append(
                QualityIssue(
                    code="NUTRITION_SUSPICIOUS_PROTEIN",
                    message="Protein per 100g unusually high",
                    severity="warning",
                    path="protein_g_per_100g",
                    details={"value": recipe.protein_g_per_100g},
                )
            )
        if recipe.fat_g_per_100g > self.thresholds.suspicious_fat_g_per_100g:
            issues.append(
                QualityIssue(
                    code="NUTRITION_SUSPICIOUS_FAT",
                    message="Fat per 100g unusually high",
                    severity="warning",
                    path="fat_g_per_100g",
                    details={"value": recipe.fat_g_per_100g},
                )
            )
        if recipe.carbs_g_per_100g > self.thresholds.suspicious_carbs_g_per_100g:
            issues.append(
                QualityIssue(
                    code="NUTRITION_SUSPICIOUS_CARBS",
                    message="Carbs per 100g unusually high",
                    severity="warning",
                    path="carbs_g_per_100g",
                    details={"value": recipe.carbs_g_per_100g},
                )
            )

        has_error = any(i.severity == "error" for i in issues)
        has_warning = any(i.severity == "warning" for i in issues)
        status = "failed" if has_error else ("warning" if has_warning else "passed")
        return CheckSummary(
            name="nutrition_snapshot_check",
            status=status,
            issues=issues,
            metrics=metrics,
        )

    async def calculate_from_ingredients(
        self,
        recipe: Recipe,
        db: aiosqlite.Connection | None = None,
    ) -> CheckSummary:
        """Ingredient-level calculation; returns insufficient_data if DB empty."""
        issues: list[QualityIssue] = []
        metrics: dict[str, Any] = {
            "ingredient_count": len(recipe.ingredients),
            "ingredients_with_nutrition": 0,
        }

        nutrition_map: dict[str, dict[str, Any]] = {}
        if db is not None:
            cur = await db.execute(
                """
                SELECT ingredient_id, calories_per_100g, protein_g_per_100g,
                       fat_g_per_100g, carbs_g_per_100g, fiber_g_per_100g
                FROM ingredient_nutrition
                """
            )
            for row in await cur.fetchall():
                nutrition_map[row[0]] = {
                    "calories_per_100g": row[1],
                    "protein_g_per_100g": row[2],
                    "fat_g_per_100g": row[3],
                    "carbs_g_per_100g": row[4],
                    "fiber_g_per_100g": row[5],
                }

        covered = 0
        missing: list[str] = []
        for ri in recipe.ingredients:
            if ri.ingredient_id in nutrition_map:
                covered += 1
            else:
                missing.append(ri.ingredient_id)
        metrics["ingredients_with_nutrition"] = covered
        metrics["missing_ingredient_ids"] = missing

        if not nutrition_map or covered < len(recipe.ingredients):
            issues.append(
                QualityIssue(
                    code="NUTRITION_INGREDIENT_DATA_INCOMPLETE",
                    message=(
                        "ingredient_nutrition table incomplete; "
                        "cannot recalculate recipe macros from ingredients"
                    ),
                    severity="warning",
                    details={"missing_count": len(missing)},
                )
            )
            return CheckSummary(
                name="nutrition_ingredient_calculation",
                status="insufficient_data",
                issues=issues,
                metrics=metrics,
            )

        # Full coverage path (unused until nutrition DB is populated).
        total_g = 0.0
        cal = prot = fat = carbs = 0.0
        for ri in recipe.ingredients:
            grams = float(ri.quantity_grams or 0)
            if grams <= 0:
                continue
            n = nutrition_map[ri.ingredient_id]
            factor = grams / 100.0
            total_g += grams
            cal += n["calories_per_100g"] * factor
            prot += n["protein_g_per_100g"] * factor
            fat += n["fat_g_per_100g"] * factor
            carbs += n["carbs_g_per_100g"] * factor

        if total_g <= 0:
            return CheckSummary(
                name="nutrition_ingredient_calculation",
                status="insufficient_data",
                issues=[
                    QualityIssue(
                        code="NUTRITION_INGREDIENT_DATA_INCOMPLETE",
                        message="No ingredient weights available for calculation",
                        severity="warning",
                    )
                ],
                metrics=metrics,
            )

        metrics.update(
            {
                "calculated_calories_per_100g": round(cal / total_g * 100, 2),
                "calculated_protein_g_per_100g": round(prot / total_g * 100, 2),
                "calculated_fat_g_per_100g": round(fat / total_g * 100, 2),
                "calculated_carbs_g_per_100g": round(carbs / total_g * 100, 2),
                "total_ingredient_mass_g": round(total_g, 2),
            }
        )
        return CheckSummary(
            name="nutrition_ingredient_calculation",
            status="passed",
            issues=issues,
            metrics=metrics,
        )
