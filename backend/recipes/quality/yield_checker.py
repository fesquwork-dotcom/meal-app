"""Yield / portion plausibility checks (structural, not kitchen-verified)."""

from __future__ import annotations

from typing import Any

from recipes.enums import IngredientUnit
from recipes.models import Recipe
from recipes.quality.models import CheckSummary, QualityIssue


class RecipeYieldChecker:
    def check(self, recipe: Recipe) -> CheckSummary:
        issues: list[QualityIssue] = []
        metrics: dict[str, Any] = {}

        yield_g = float(recipe.yield_weight_g)
        base = float(recipe.base_servings)
        portion_min = float(recipe.recommended_portion_min_g)
        portion_max = float(recipe.recommended_portion_max_g)

        if yield_g <= 0 or base <= 0:
            issues.append(
                QualityIssue(
                    code="YIELD_INVALID",
                    message="yield_weight_g and base_servings must be > 0",
                    severity="error",
                )
            )
            return CheckSummary(
                name="yield_sanity",
                status="failed",
                issues=issues,
                metrics=metrics,
            )

        base_portion = yield_g / base
        metrics["base_portion_g"] = round(base_portion, 2)
        metrics["recommended_portion_min_g"] = portion_min
        metrics["recommended_portion_max_g"] = portion_max
        metrics["yield_weight_g"] = yield_g

        if base_portion < portion_min * 0.85 or base_portion > portion_max * 1.15:
            issues.append(
                QualityIssue(
                    code="BASE_PORTION_OUTSIDE_RECOMMENDED_RANGE",
                    message=(
                        f"Base portion {base_portion:.0f}g outside recommended "
                        f"range {portion_min:.0f}–{portion_max:.0f}g"
                    ),
                    severity="warning",
                    details={
                        "base_portion_g": base_portion,
                        "min": portion_min,
                        "max": portion_max,
                    },
                )
            )

        ingredient_mass = 0.0
        mass_known = 0
        piece_missing = 0
        for ri in recipe.ingredients:
            if ri.quantity_grams is not None and float(ri.quantity_grams) > 0:
                ingredient_mass += float(ri.quantity_grams)
                mass_known += 1
            elif ri.unit == IngredientUnit.PIECE:
                piece_missing += 1
                if ri.ingredient and ri.ingredient.piece_weight_g:
                    ingredient_mass += float(ri.quantity) * float(
                        ri.ingredient.piece_weight_g
                    )
                    mass_known += 1
                else:
                    issues.append(
                        QualityIssue(
                            code="PIECE_WEIGHT_MISSING",
                            message=f"Piece ingredient {ri.ingredient_id} lacks grams",
                            severity="warning",
                            path=ri.ingredient_id,
                        )
                    )

        metrics["ingredient_mass_g"] = round(ingredient_mass, 2)
        metrics["ingredients_with_mass"] = mass_known
        metrics["piece_weight_missing_count"] = piece_missing

        coverage = mass_known / max(len(recipe.ingredients), 1)
        metrics["ingredient_weight_coverage"] = round(coverage, 3)
        if coverage < 0.7:
            issues.append(
                QualityIssue(
                    code="INGREDIENT_WEIGHT_COVERAGE_LOW",
                    message="Fewer than 70% of ingredients have mass estimates",
                    severity="warning",
                    details={"coverage": coverage},
                )
            )

        status_label = "plausible"
        if ingredient_mass > 0 and coverage >= 0.7:
            ratio = yield_g / ingredient_mass
            metrics["yield_to_ingredient_mass_ratio"] = round(ratio, 3)
            # Cooking can lose moisture (~0.5) or absorb liquid (~1.5+ for grains).
            if ratio < 0.35:
                status_label = "suspicious"
                issues.append(
                    QualityIssue(
                        code="YIELD_TOO_LOW_FOR_INGREDIENT_MASS",
                        message=(
                            f"Yield {yield_g:.0f}g is much lower than ingredient "
                            f"mass {ingredient_mass:.0f}g"
                        ),
                        severity="warning",
                        details={"ratio": ratio},
                    )
                )
            elif ratio > 2.5:
                status_label = "suspicious"
                issues.append(
                    QualityIssue(
                        code="YIELD_TOO_HIGH_FOR_INGREDIENT_MASS",
                        message=(
                            f"Yield {yield_g:.0f}g is much higher than ingredient "
                            f"mass {ingredient_mass:.0f}g"
                        ),
                        severity="warning",
                        details={"ratio": ratio},
                    )
                )
        else:
            status_label = "insufficient_data"
            issues.append(
                QualityIssue(
                    code="COOKING_YIELD_NOT_VERIFIED",
                    message=(
                        "Cooking yield cannot be verified without complete "
                        "ingredient masses / kitchen coefficients"
                    ),
                    severity="info",
                )
            )

        metrics["plausibility"] = status_label
        has_error = any(i.severity == "error" for i in issues)
        has_warning = any(i.severity == "warning" for i in issues)
        check_status = (
            "failed"
            if has_error
            else (
                "insufficient_data"
                if status_label == "insufficient_data" and not has_warning
                else ("warning" if has_warning else "passed")
            )
        )
        return CheckSummary(
            name="yield_sanity",
            status=check_status,
            issues=issues,
            metrics=metrics,
        )
