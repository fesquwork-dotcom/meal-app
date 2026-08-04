"""Basic ingredient proportion sanity checks."""

from __future__ import annotations

from collections import Counter
from typing import Any

from recipes.enums import CookingMethod, IngredientGroup, IngredientUnit
from recipes.models import Recipe
from recipes.quality.config import DEFAULT_QUALITY_THRESHOLDS, QualityThresholds
from recipes.quality.models import CheckSummary, QualityIssue

DRY_GRAIN_IDS = frozenset(
    {
        "ing_oats",
        "ing_rice",
        "ing_buckwheat",
        "ing_pasta",
        "ing_lentils",
        "ing_beans",
    }
)
LIQUID_IDS = frozenset(
    {
        "ing_water",
        "ing_milk",
        "ing_broth",
        "ing_stock",
        "ing_tomato",
        "ing_tomato_sauce",
        "ing_yogurt",
    }
)
OIL_IDS = frozenset({"ing_oil", "ing_olive_oil", "ing_sunflower_oil", "ing_butter"})
SEASONING_IDS = frozenset(
    {"ing_salt", "ing_pepper", "ing_spice", "ing_paprika", "ing_cumin"}
)


class RecipeProportionChecker:
    def __init__(self, thresholds: QualityThresholds | None = None) -> None:
        self.thresholds = thresholds or DEFAULT_QUALITY_THRESHOLDS

    def check(self, recipe: Recipe) -> CheckSummary:
        issues: list[QualityIssue] = []
        metrics: dict[str, Any] = {}

        masses: dict[str, float] = {}
        total_mass = 0.0
        for ri in recipe.ingredients:
            grams = float(ri.quantity_grams or 0)
            if grams <= 0 and ri.unit == IngredientUnit.ML:
                grams = float(ri.quantity)
            if grams > 0:
                masses[ri.ingredient_id] = masses.get(ri.ingredient_id, 0.0) + grams
                total_mass += grams

        metrics["total_ingredient_mass_g"] = round(total_mass, 2)

        # Duplicate ingredients
        counts = Counter(ri.ingredient_id for ri in recipe.ingredients)
        for iid, cnt in counts.items():
            if cnt > 1:
                groups = {
                    ri.ingredient_group
                    for ri in recipe.ingredients
                    if ri.ingredient_id == iid
                }
                if len(groups) <= 1:
                    issues.append(
                        QualityIssue(
                            code="DUPLICATE_RECIPE_INGREDIENT",
                            message=f"Ingredient {iid} appears {cnt} times",
                            severity="warning",
                            path=iid,
                        )
                    )

        if total_mass > 0:
            seasoning_mass = sum(
                m
                for iid, m in masses.items()
                if iid in SEASONING_IDS
                or any(
                    ri.ingredient_group == IngredientGroup.SEASONING
                    and ri.ingredient_id == iid
                    for ri in recipe.ingredients
                )
            )
            oil_mass = sum(m for iid, m in masses.items() if iid in OIL_IDS)
            # Also catch oil by name substring
            for ri in recipe.ingredients:
                name = (ri.ingredient.canonical_name if ri.ingredient else ri.ingredient_id).lower()
                grams = float(ri.quantity_grams or 0)
                if "oil" in name or "butter" in name or "масло" in name:
                    oil_mass = max(oil_mass, oil_mass)  # ensure counted
                    if ri.ingredient_id not in OIL_IDS and grams > 0:
                        oil_mass += grams

            seasoning_share = seasoning_mass / total_mass
            oil_share = oil_mass / total_mass
            metrics["seasoning_share"] = round(seasoning_share, 4)
            metrics["oil_share"] = round(oil_share, 4)

            if seasoning_share > self.thresholds.seasoning_mass_share_warning:
                issues.append(
                    QualityIssue(
                        code="SEASONING_QUANTITY_SUSPICIOUS",
                        message=f"Seasoning mass share {seasoning_share:.1%} looks high",
                        severity="warning",
                        details={"share": seasoning_share},
                    )
                )
            if oil_share > self.thresholds.oil_mass_share_warning:
                issues.append(
                    QualityIssue(
                        code="OIL_RATIO_SUSPICIOUS",
                        message=f"Oil/fat mass share {oil_share:.1%} looks high",
                        severity="warning",
                        details={"share": oil_share},
                    )
                )

            main_ings = [
                ri
                for ri in recipe.ingredients
                if ri.ingredient_group == IngredientGroup.MAIN and not ri.is_optional
            ]
            for ri in main_ings:
                grams = float(ri.quantity_grams or 0)
                if grams <= 0:
                    issues.append(
                        QualityIssue(
                            code="MAIN_INGREDIENT_SHARE_SUSPICIOUS",
                            message=f"Main ingredient {ri.ingredient_id} has no mass",
                            severity="warning",
                            path=ri.ingredient_id,
                        )
                    )
                elif grams / total_mass < 0.02:
                    issues.append(
                        QualityIssue(
                            code="MAIN_INGREDIENT_SHARE_SUSPICIOUS",
                            message=(
                                f"Main ingredient {ri.ingredient_id} is only "
                                f"{grams / total_mass:.1%} of mass"
                            ),
                            severity="warning",
                            path=ri.ingredient_id,
                        )
                    )

            has_dry_grain = any(ri.ingredient_id in DRY_GRAIN_IDS for ri in recipe.ingredients)
            has_liquid = any(
                ri.ingredient_id in LIQUID_IDS
                or (ri.unit == IngredientUnit.ML and float(ri.quantity) > 0)
                or "water" in ri.ingredient_id
                or "milk" in ri.ingredient_id
                or "broth" in ri.ingredient_id
                for ri in recipe.ingredients
            )
            boiling = CookingMethod.BOILING in recipe.cooking_methods
            if has_dry_grain and boiling and not has_liquid:
                issues.append(
                    QualityIssue(
                        code="DRY_GRAIN_LIQUID_NOT_FOUND",
                        message="Dry grain with boiling but no liquid ingredient found",
                        severity="warning",
                    )
                )

            for ri in recipe.ingredients:
                if ri.unit == IngredientUnit.PIECE and ri.quantity_grams is None:
                    if "egg" in ri.ingredient_id:
                        issues.append(
                            QualityIssue(
                                code="PROPORTION_REQUIRES_SOURCE_REVIEW",
                                message=f"Egg {ri.ingredient_id} missing quantity_grams",
                                severity="warning",
                                path=ri.ingredient_id,
                            )
                        )

        issues.append(
            QualityIssue(
                code="PROPORTION_REQUIRES_SOURCE_REVIEW",
                message="Proportion checks are coarse heuristics only",
                severity="info",
            )
        )

        has_error = any(i.severity == "error" for i in issues)
        has_warning = any(i.severity == "warning" for i in issues)
        status = "failed" if has_error else ("warning" if has_warning else "passed")
        return CheckSummary(
            name="proportion_sanity",
            status=status,
            issues=issues,
            metrics=metrics,
        )
