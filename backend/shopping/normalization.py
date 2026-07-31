"""Ingredient name normalization and alias registry."""

from __future__ import annotations

import re

from menu_models import normalize_meal_name
from shopping.display_names import glossary_note, resolve_display_name

# Maps alias → canonical product key (without merging distinct products).
INGREDIENT_ALIASES: dict[str, str] = {
    "томат": "помидор",
    "томаты": "помидор",
    "помидоры": "помидор",
    "куриное филе": "куриная грудка",
    "филе курицы": "куриная грудка",
    "гр": "грамм",
}

_QUALIFIER_PATTERN = re.compile(
    r"\b(\d+\s*%|заморожен\w*|свеж\w*|цельнозерн\w*|безлактозн\w*)\b",
    re.IGNORECASE,
)
_HYPHEN_PATTERN = re.compile(r"[-–—]+")


def canonical_ingredient_name(name: str) -> str:
    """Returns a stable key for deduplication while preserving meaningful qualifiers."""
    normalized = normalize_meal_name(name)
    normalized = _HYPHEN_PATTERN.sub(" ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()

    if normalized in INGREDIENT_ALIASES:
        normalized = INGREDIENT_ALIASES[normalized]

    # Do not collapse products that differ by fat % or similar qualifiers.
    return normalized


def display_ingredient_name(name: str) -> str:
    """Human-readable label for UI; never returns internal canonical keys as-is."""
    return resolve_display_name(name)


def ingredient_glossary_note(name: str) -> str | None:
    """Optional explanation for uncommon ingredients."""
    return glossary_note(name)


def are_merge_compatible(left: str, right: str) -> bool:
    """True when two ingredient names refer to the same purchasable product."""
    return canonical_ingredient_name(left) == canonical_ingredient_name(right)
