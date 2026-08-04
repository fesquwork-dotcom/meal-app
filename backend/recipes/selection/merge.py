"""Merge Profile + Strategy + meal-slot overrides into one context.

Precedence (documented):
  Meal slot explicit override > WeeklyStrategy > Profile defaults

Hard exclusions / avoid sets are UNIONED (never overwritten by a lower layer).
Scalar preferences use highest-priority non-None value.
"""

from __future__ import annotations

from typing import Any

from recipes.enums import MealType
from recipes.selection.context import CandidateSelectionContext


_SET_UNION_FIELDS = (
    "preferred_ingredient_ids",
    "excluded_ingredient_ids",
    "avoid_ingredient_ids",
    "avoid_recipe_ids",
    "preferred_protein_sources",
    "excluded_protein_sources",
    "required_tags",
    "excluded_tags",
    "preferred_tags",
)

_LIST_UNION_FIELDS = ("desired_roles",)

_SCALAR_FIELDS = (
    "goal",
    "allowed_budget_classes",
    "max_total_time_minutes",
    "available_equipment",
    "allow_leftovers",
    "prefer_batch_friendly",
    "family_mode",
    "limit",
)


def _as_partial(source: CandidateSelectionContext | dict[str, Any] | None) -> dict[str, Any]:
    if source is None:
        return {}
    if isinstance(source, CandidateSelectionContext):
        return source.model_dump()
    return dict(source)


def merge_selection_contexts(
    *,
    meal_type: MealType | str,
    profile: CandidateSelectionContext | dict[str, Any] | None = None,
    strategy: CandidateSelectionContext | dict[str, Any] | None = None,
    slot: CandidateSelectionContext | dict[str, Any] | None = None,
    limit: int | None = None,
) -> CandidateSelectionContext:
    """Merge layers with documented precedence.

    Exclusions and avoid-sets are combined across all layers.
    """
    layers = [_as_partial(profile), _as_partial(strategy), _as_partial(slot)]
    merged: dict[str, Any] = {"meal_type": MealType(meal_type)}

    for field in _SET_UNION_FIELDS:
        combined: set[Any] = set()
        for layer in layers:
            value = layer.get(field)
            if value:
                combined |= set(value) if not isinstance(value, set) else value
        merged[field] = combined

    for field in _LIST_UNION_FIELDS:
        combined_list: list[Any] = []
        seen: set[Any] = set()
        for layer in layers:
            for item in layer.get(field) or []:
                if item not in seen:
                    seen.add(item)
                    combined_list.append(item)
        merged[field] = combined_list

    for field in _SCALAR_FIELDS:
        # Highest priority non-None wins (slot > strategy > profile).
        chosen = None
        found = False
        for layer in reversed(layers):
            if field in layer and layer[field] is not None:
                chosen = layer[field]
                found = True
                break
        if found:
            merged[field] = chosen

    if limit is not None:
        merged["limit"] = limit
    elif "limit" not in merged:
        merged["limit"] = 5

    return CandidateSelectionContext.model_validate(merged)
