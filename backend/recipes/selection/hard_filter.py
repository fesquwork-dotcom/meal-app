"""Hard filters — recipe is fully excluded when any check fails."""

from __future__ import annotations

from recipes.enums import EquipmentType, RecipeStatus, TagType
from recipes.models import Recipe
from recipes.selection.codes import HardFilterCode
from recipes.selection.context import CandidateSelectionContext
from recipes.selection.models import RecipeFilterDecision

# Profile does not track basic prep tools. Treat as always available so
# recipes requiring only knife/cutting_board are not falsely rejected when
# available_equipment is a kitchen-appliance subset (stove/pan/pot/oven).
IMPLICIT_BASIC_EQUIPMENT: frozenset[EquipmentType] = frozenset(
    {
        EquipmentType.KNIFE,
        EquipmentType.CUTTING_BOARD,
        EquipmentType.GRATER,
    }
)


class RecipeHardFilter:
    """Deterministic hard filters with explainable rejection codes."""

    def evaluate(
        self,
        recipe: Recipe,
        context: CandidateSelectionContext,
    ) -> RecipeFilterDecision:
        codes: list[str] = []

        if recipe.status != RecipeStatus.ACTIVE:
            codes.append(HardFilterCode.INACTIVE_RECIPE.value)

        meal_ok = any(m.meal_type == context.meal_type for m in recipe.meal_types)
        if not meal_ok and recipe.primary_meal_type == context.meal_type:
            # Defensive: primary without meal_types link still counts.
            meal_ok = True
        if not meal_ok:
            codes.append(HardFilterCode.MEAL_TYPE_MISMATCH.value)

        if recipe.id in context.avoid_recipe_ids:
            codes.append(HardFilterCode.AVOIDED_RECIPE.value)

        if context.max_total_time_minutes is not None:
            if recipe.total_time_minutes > context.max_total_time_minutes:
                codes.append(HardFilterCode.TIME_LIMIT_EXCEEDED.value)

        if context.allowed_budget_classes is not None:
            allowed = set(context.allowed_budget_classes)
            if recipe.budget_class not in allowed:
                codes.append(HardFilterCode.BUDGET_CLASS_NOT_ALLOWED.value)

        if context.excluded_ingredient_ids:
            for item in recipe.ingredients:
                if item.is_optional:
                    continue
                if item.ingredient_id in context.excluded_ingredient_ids:
                    codes.append(HardFilterCode.EXCLUDED_INGREDIENT.value)
                    break

        if context.excluded_protein_sources:
            protein_tags = {
                t.tag_value
                for t in recipe.tags
                if t.tag_type == TagType.PROTEIN_SOURCE
            }
            excluded = {p.value for p in context.excluded_protein_sources}
            if protein_tags & excluded:
                codes.append(HardFilterCode.EXCLUDED_PROTEIN_SOURCE.value)

        recipe_tag_pairs = {(t.tag_type.value, t.tag_value) for t in recipe.tags}

        if context.required_tags:
            for pair in context.required_tags:
                if pair not in recipe_tag_pairs:
                    codes.append(HardFilterCode.REQUIRED_TAG_MISSING.value)
                    break

        if context.excluded_tags:
            for pair in context.excluded_tags:
                if pair in recipe_tag_pairs:
                    codes.append(HardFilterCode.EXCLUDED_TAG_PRESENT.value)
                    break

        if context.available_equipment is not None:
            available = set(context.available_equipment) | IMPLICIT_BASIC_EQUIPMENT
            for eq in recipe.equipment:
                if not eq.required:
                    continue
                if eq.equipment not in available:
                    codes.append(HardFilterCode.REQUIRED_EQUIPMENT_UNAVAILABLE.value)
                    break

        # Deduplicate while preserving order
        seen: set[str] = set()
        unique: list[str] = []
        for code in codes:
            if code not in seen:
                seen.add(code)
                unique.append(code)

        return RecipeFilterDecision(
            recipe_id=recipe.id,
            accepted=not unique,
            reason_codes=unique,
        )
