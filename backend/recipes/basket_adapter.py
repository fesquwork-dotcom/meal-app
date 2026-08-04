"""Adapter: Recipe Catalog → Basket Engine NormalizedIngredient.

Does not modify Basket Engine. Maps catalog units to shopping units.
"""

from __future__ import annotations

from decimal import Decimal

from shopping.models import NormalizedIngredient
from shopping.normalization import canonical_ingredient_name
from shopping.units import normalize_unit

from recipes.enums import IngredientUnit
from recipes.models import Recipe, ScaledRecipe, ScaledRecipeIngredient

# Catalog uses `piece`; Basket Engine canonical unit is `pcs`.
_UNIT_TO_BASKET: dict[str, str] = {
    IngredientUnit.G.value: "g",
    IngredientUnit.ML.value: "ml",
    IngredientUnit.PIECE.value: "pcs",
    IngredientUnit.TSP.value: "tsp",
    IngredientUnit.TBSP.value: "tbsp",
}


def catalog_unit_to_basket(unit: IngredientUnit | str) -> str:
    raw = unit.value if isinstance(unit, IngredientUnit) else str(unit)
    mapped = _UNIT_TO_BASKET.get(raw, raw)
    return normalize_unit(mapped)


def scaled_ingredient_to_normalized(
    item: ScaledRecipeIngredient,
    *,
    recipe_name: str,
    meal_id: str | None = None,
    display_name: str | None = None,
) -> NormalizedIngredient:
    """Maps one scaled catalog ingredient into Basket Engine form."""
    name = display_name or item.display_name or item.ingredient_id
    unit = catalog_unit_to_basket(item.unit)
    # Prefer grams when available for aggregatable mass merges.
    quantity = item.quantity
    out_unit = unit
    if item.quantity_grams is not None and unit in {"pcs", "tsp", "tbsp"}:
        # Keep original unit; grams stay available via quantity when unit is g.
        pass
    if item.unit == IngredientUnit.G or (
        item.quantity_grams is not None and item.unit == IngredientUnit.G
    ):
        quantity = item.quantity_grams if item.quantity_grams is not None else item.quantity
        out_unit = "g"
    elif item.quantity_grams is not None and item.unit == IngredientUnit.ML:
        # Keep ml; density conversion is a future layer.
        quantity = item.quantity
        out_unit = "ml"

    return NormalizedIngredient(
        canonical_name=canonical_ingredient_name(name),
        display_name=name,
        quantity=Decimal(str(quantity)),
        unit=out_unit,
        aggregatable=out_unit not in {"to_taste", "unknown"},
        source_recipe_names=(recipe_name,),
        source_meal_ids=(meal_id,) if meal_id else (),
    )


def recipe_to_normalized_ingredients(
    recipe: Recipe,
    scaled: ScaledRecipe,
    *,
    meal_id: str | None = None,
) -> list[NormalizedIngredient]:
    """Converts a scaled recipe into NormalizedIngredient list for Basket Engine."""
    by_id = {i.id: i for i in recipe.ingredients}
    result: list[NormalizedIngredient] = []
    for item in scaled.ingredients:
        base = by_id.get(item.recipe_ingredient_id)
        display = item.display_name
        if display is None and base is not None and base.ingredient is not None:
            display = base.ingredient.display_name
        if display is None and base is not None:
            display = base.ingredient_id
        result.append(
            scaled_ingredient_to_normalized(
                item,
                recipe_name=recipe.name,
                meal_id=meal_id,
                display_name=display,
            )
        )
    return result


def merge_normalized_for_test(
    items: list[NormalizedIngredient],
) -> dict[str, NormalizedIngredient]:
    """Simple aggregation by canonical_name+unit for integration tests."""
    merged: dict[str, NormalizedIngredient] = {}
    for item in items:
        key = f"{item.canonical_name}|{item.unit}"
        existing = merged.get(key)
        if existing is None:
            merged[key] = item
            continue
        qty = (existing.quantity or Decimal("0")) + (item.quantity or Decimal("0"))
        names = tuple(dict.fromkeys(existing.source_recipe_names + item.source_recipe_names))
        meals = tuple(dict.fromkeys(existing.source_meal_ids + item.source_meal_ids))
        merged[key] = NormalizedIngredient(
            canonical_name=existing.canonical_name,
            display_name=existing.display_name,
            quantity=qty,
            unit=existing.unit,
            aggregatable=existing.aggregatable and item.aggregatable,
            source_recipe_names=names,
            source_meal_ids=meals,
        )
    return merged
