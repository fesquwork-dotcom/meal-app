"""Allowlisted, deterministic user-facing texts for Learned Preferences.

No free-form strings and no LLM summaries: every text is keyed by type. This
mirrors the presentation allowlists used by Trends and Insights.
"""

from __future__ import annotations

from learned_preferences.models import LearnedPreferenceType

LEARNED_PREFERENCE_TITLES: dict[LearnedPreferenceType, str] = {
    "prefer_familiar_meals": "Знакомые ингредиенты подходят чаще",
    "avoid_unavailable_products": "Недоступные продукты лучше исключать",
    "prefer_fast_meals": "Быстрые блюда заменяются реже",
    "stable_cook_days": "Дни готовки остаются стабильными",
    "stable_shopping_days": "Дни закупок остаются стабильными",
}

LEARNED_PREFERENCE_SUMMARIES: dict[LearnedPreferenceType, str] = {
    "prefer_familiar_meals": (
        "Мы заметили, что блюда со знакомыми ингредиентами чаще подходят вам."
    ),
    "avoid_unavailable_products": (
        "Мы заметили, что блюда с недоступными продуктами вы почти всегда меняете."
    ),
    "prefer_fast_meals": (
        "Мы заметили, что быстрые в приготовлении блюда вы заменяете реже."
    ),
    "stable_cook_days": (
        "Мы заметили, что вы готовите примерно в одни и те же дни недели."
    ),
    "stable_shopping_days": (
        "Мы заметили, что вы закупаетесь примерно в одни и те же дни недели."
    ),
}

# Human-safe basis label for evidence; never a raw decision identifier.
LEARNED_PREFERENCE_BASIS: dict[LearnedPreferenceType, str] = {
    "prefer_familiar_meals": "выбор знакомых блюд",
    "avoid_unavailable_products": "доступность продуктов",
    "prefer_fast_meals": "скорость приготовления",
    "stable_cook_days": "дни готовки",
    "stable_shopping_days": "дни закупок",
}
