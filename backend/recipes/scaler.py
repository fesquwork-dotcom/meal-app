"""Deterministic recipe scaling (does not mutate source Recipe)."""

from __future__ import annotations

from decimal import ROUND_CEILING, Decimal

from recipes.enums import ScalingMode
from recipes.models import Recipe, ScaledRecipe, ScaledRecipeIngredient


class RecipeScaleError(ValueError):
    """Raised when target servings cannot be applied."""


class RecipeScaler:
    """Scales recipe ingredients for a target servings count."""

    def scale(self, recipe: Recipe, target_servings: float | Decimal) -> ScaledRecipe:
        target = Decimal(str(target_servings))
        if target <= 0:
            raise RecipeScaleError("target_servings must be > 0")

        base = recipe.base_servings
        if recipe.scaling_mode == ScalingMode.LIMITED:
            if target < recipe.min_batch_servings or target > recipe.max_batch_servings:
                raise RecipeScaleError(
                    f"target_servings {target} outside "
                    f"[{recipe.min_batch_servings}, {recipe.max_batch_servings}]"
                )

        factor = target / base
        scaled: list[ScaledRecipeIngredient] = []
        for item in recipe.ingredients:
            qty = item.quantity * item.scaling_factor * factor
            grams = (
                None
                if item.quantity_grams is None
                else item.quantity_grams * item.scaling_factor * factor
            )

            if recipe.scaling_mode == ScalingMode.DISCRETE and item.rounding_increment:
                qty = self._round_up(qty, item.rounding_increment)
                if grams is not None and item.quantity > 0:
                    # Keep grams proportional to rounded discrete quantity.
                    grams = item.quantity_grams * (qty / item.quantity)
            elif recipe.scaling_mode == ScalingMode.LINEAR and item.rounding_increment:
                # Discrete components inside an otherwise linear recipe.
                qty = self._round_up(qty, item.rounding_increment)
                if grams is not None and item.quantity > 0:
                    grams = item.quantity_grams * (qty / item.quantity)

            display = None
            if item.ingredient is not None:
                display = item.ingredient.display_name

            scaled.append(
                ScaledRecipeIngredient(
                    recipe_ingredient_id=item.id,
                    ingredient_id=item.ingredient_id,
                    quantity=qty,
                    unit=item.unit,
                    quantity_grams=grams,
                    is_optional=item.is_optional,
                    ingredient_group=item.ingredient_group,
                    sort_order=item.sort_order,
                    display_name=display,
                )
            )

        return ScaledRecipe(
            recipe_id=recipe.id,
            base_servings=base,
            target_servings=target,
            ingredients=scaled,
        )

    @staticmethod
    def _round_up(value: Decimal, increment: Decimal) -> Decimal:
        if increment <= 0:
            return value
        # Round up to nearest increment (prefer over-portion for mandatory items).
        steps = (value / increment).to_integral_value(rounding=ROUND_CEILING)
        return steps * increment
