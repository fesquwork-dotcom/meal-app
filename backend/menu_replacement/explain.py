"""Template-based replacement explanations (no LLM)."""

from __future__ import annotations

from menu_replacement.reasons import CatalogReplacementReason
from recipes.models import Recipe


def build_replacement_explanation(
    *,
    old_recipe: Recipe | None,
    new_recipe: Recipe,
    reason: CatalogReplacementReason,
    machine_reasons: tuple[str, ...],
) -> str:
    old_name = old_recipe.name if old_recipe is not None else "текущее блюдо"
    new_name = new_recipe.name

    if "FASTER_THAN_CURRENT" in machine_reasons or reason == CatalogReplacementReason.TOO_LONG:
        return (
            f"Заменили «{old_name}» на «{new_name}»: блюдо готовится быстрее "
            "и соответствует вашему недельному плану."
        )
    if "CHEAPER_BUDGET_CLASS" in machine_reasons or reason == CatalogReplacementReason.TOO_EXPENSIVE:
        return (
            f"Заменили «{old_name}» на «{new_name}»: более доступный вариант "
            "в рамках бюджета недели."
        )
    if reason == CatalogReplacementReason.INGREDIENT_UNAVAILABLE:
        return (
            f"Заменили «{old_name}» на «{new_name}»: без недоступного ингредиента "
            "и с учётом ограничений недели."
        )
    if reason in {
        CatalogReplacementReason.DONT_LIKE,
        CatalogReplacementReason.WANT_VARIETY,
    }:
        return (
            f"Заменили «{old_name}» на «{new_name}»: другое блюдо того же типа "
            "приёма пищи, совместимое с недельным планом."
        )
    return (
        f"Заменили «{old_name}» на «{new_name}»: вариант соответствует профилю "
        "и недельному плану."
    )
