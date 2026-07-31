"""Deterministic shopping advice and purchase badges (presentation only)."""

from __future__ import annotations

from shopping.normalization import canonical_ingredient_name

# Advice labels (stable Russian copy for UI).
ADVICE_BUY_EARLY = "Купить заранее"
ADVICE_CHILLED = "Лучше купить охлаждённым"
ADVICE_BULK = "Можно взять большую упаковку"
ADVICE_LARGE_STORE = "Проще найти в крупных супермаркетах"
ADVICE_FRESH = "Нужно купить свежим"

_SPECIALTY_FRAGMENTS = (
    "тахини",
    "киноа",
    "булгур",
    "мисо",
    "тофу",
    "темпе",
    "нори",
    "мирин",
    "кимчи",
    "васаби",
    "гарам масала",
    "харисса",
    "харрисса",
    "тамаринд",
    "сумах",
    "суммах",
)

_FRESH_FRAGMENTS = (
    "зелен",
    "укроп",
    "петрушк",
    "кинз",
    "базилик",
    "шпинат",
    "салат",
    "руккол",
    "мята",
    "ягод",
    "клубник",
    "малин",
)

_BULK_FRAGMENTS = (
    "рис",
    "греч",
    "овсян",
    "булгур",
    "киноа",
    "нут",
    "чечевиц",
    "мук",
    "макарон",
    "паста",
    "круп",
)


def shopping_advice_for(display_name: str, category: str) -> list[str]:
    """Return zero or more shopping tips for a basket line."""
    lowered = display_name.lower()
    canonical = canonical_ingredient_name(display_name)
    cat = category.lower()
    advice: list[str] = []

    if any(fragment in canonical or fragment in lowered for fragment in _SPECIALTY_FRAGMENTS):
        advice.append(ADVICE_LARGE_STORE)

    if cat in {"мясо", "рыба", "молочное", "молочные продукты"} or any(
        fragment in lowered for fragment in ("кури", "говяд", "свинин", "индейк", "рыб", "лосос", "треск", "кревет")
    ):
        advice.append(ADVICE_CHILLED)

    if cat in {"овощи", "фрукты"} or any(fragment in lowered for fragment in _FRESH_FRAGMENTS):
        if ADVICE_FRESH not in advice:
            advice.append(ADVICE_FRESH)
        if any(fragment in lowered for fragment in _FRESH_FRAGMENTS):
            advice.append(ADVICE_BUY_EARLY)

    if cat in {"крупы", "бакалея"} or any(fragment in lowered for fragment in _BULK_FRAGMENTS):
        advice.append(ADVICE_BULK)

    # Deduplicate while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for item in advice:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique[:3]


def purchase_badges(*, used_in_recipes: int, shopping_advice: list[str]) -> list[str]:
    """Compact badges that help decide what to buy in the store."""
    badges: list[str] = []
    if used_in_recipes >= 3:
        badges.append(f"Используется в {used_in_recipes} блюдах")
    elif used_in_recipes == 2:
        badges.append("Есть в нескольких рецептах")
    elif used_in_recipes == 1:
        badges.append("Покупается один раз")

    if ADVICE_FRESH in shopping_advice:
        badges.append(ADVICE_FRESH)
    elif ADVICE_CHILLED in shopping_advice:
        badges.append(ADVICE_CHILLED)

    return badges[:3]
