"""Resolve free-text product names to catalog ingredient IDs."""

from __future__ import annotations

from dataclasses import dataclass, field

from menu_models import normalize_meal_name
from recipes.models import Ingredient
from shopping.normalization import canonical_ingredient_name


@dataclass
class IngredientResolveResult:
    resolved_ids: set[str] = field(default_factory=set)
    unresolved: list[str] = field(default_factory=list)
    resolved_map: dict[str, str] = field(default_factory=dict)


def build_ingredient_lookup(
    ingredients: list[Ingredient],
) -> dict[str, str]:
    """normalized text → ingredient_id."""
    lookup: dict[str, str] = {}
    for ing in ingredients:
        keys = {
            normalize_meal_name(ing.canonical_name),
            normalize_meal_name(ing.display_name),
            canonical_ingredient_name(ing.display_name),
            canonical_ingredient_name(ing.canonical_name),
        }
        for alias in ing.aliases:
            keys.add(normalize_meal_name(alias.alias))
            keys.add(alias.normalized_alias)
            keys.add(canonical_ingredient_name(alias.alias))
        for key in keys:
            if key:
                lookup[key] = ing.id
    return lookup


def resolve_product_names(
    names: list[str] | tuple[str, ...] | set[str],
    ingredients: list[Ingredient],
) -> IngredientResolveResult:
    lookup = build_ingredient_lookup(ingredients)
    result = IngredientResolveResult()
    for raw in names:
        if not isinstance(raw, str) or not raw.strip():
            continue
        text = raw.strip()
        keys = {
            normalize_meal_name(text),
            canonical_ingredient_name(text),
        }
        found: str | None = None
        for key in keys:
            if key in lookup:
                found = lookup[key]
                break
        # Substring fallback for common cases like "грибы" → mushroom display
        if found is None:
            norm = normalize_meal_name(text)
            for key, iid in lookup.items():
                if norm and (norm in key or key in norm) and len(norm) >= 4:
                    found = iid
                    break
        if found is None:
            result.unresolved.append(text)
        else:
            result.resolved_ids.add(found)
            result.resolved_map[text] = found
    return result
