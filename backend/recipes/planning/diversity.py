"""Diversity helpers for weekly planning (thin utilities)."""

from __future__ import annotations

from collections import Counter

from recipes.enums import MealType
from recipes.models import Recipe
from recipes.planning.candidate_provider import primary_protein
from recipes.planning.models import WeeklyPlannedMeal


def protein_sequence(meals: list[WeeklyPlannedMeal], recipes: dict[str, Recipe]) -> list[str]:
    out: list[str] = []
    for m in sorted(meals, key=lambda x: (x.day_index, x.meal_type)):
        r = recipes.get(m.recipe_id)
        if not r:
            out.append("unknown")
            continue
        if m.meal_type == MealType.BREAKFAST.value:
            out.append(f"bf:{primary_protein(r) or 'none'}")
        else:
            out.append(primary_protein(r) or "none")
    return out


def count_independent_recipe_repeats(meals: list[WeeklyPlannedMeal]) -> Counter[str]:
    c: Counter[str] = Counter()
    for m in meals:
        if not m.is_leftover:
            c[m.recipe_id] += 1
    return c
