"""Weekly plan validation — structured violations, not a bare bool."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from recipes.models import Recipe
from recipes.planning.codes import PlannerViolationCode
from recipes.planning.constraints import (
    has_excluded_ingredient,
    has_excluded_protein,
    meal_type_supported,
)
from recipes.planning.context import WeeklyPlanningContext
from recipes.planning.models import WeeklyRecipePlan
from recipes.planning.relations import RelationIndex
from recipes.planning.slots import WeeklyMealSlot
from recipes.enums import MealType


class PlanViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    slot_id: str | None = None
    detail: str = ""


class ValidationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ok: bool = True
    violations: list[PlanViolation] = Field(default_factory=list)


class WeeklyRecipePlanValidator:
    def validate(
        self,
        plan: WeeklyRecipePlan,
        *,
        context: WeeklyPlanningContext,
        recipes: dict[str, Recipe],
        relation_index: RelationIndex,
        slots: list[WeeklyMealSlot],
    ) -> ValidationReport:
        violations: list[PlanViolation] = []
        by_slot = plan.meal_by_slot()
        slot_order = {s.slot_id: s.order_index for s in slots}

        for slot in slots:
            if not slot.requires_recipe:
                continue
            if slot.slot_id not in by_slot:
                if plan.status.value == "success":
                    violations.append(
                        PlanViolation(
                            code=PlannerViolationCode.SLOT_UNFILLED,
                            slot_id=slot.slot_id,
                        )
                    )

        inst_by_id = {c.cooking_instance_id: c for c in plan.cooking_instances}
        leftover_counts: dict[str, int] = {}

        for meal in plan.meals:
            recipe = recipes.get(meal.recipe_id)
            if recipe is None:
                violations.append(
                    PlanViolation(
                        code=PlannerViolationCode.RECIPE_MISSING,
                        slot_id=meal.slot_id,
                        detail=meal.recipe_id,
                    )
                )
                continue
            mt = MealType(meal.meal_type)
            if not meal_type_supported(recipe, mt):
                violations.append(
                    PlanViolation(
                        code=PlannerViolationCode.MEAL_TYPE_INVALID,
                        slot_id=meal.slot_id,
                    )
                )
            if has_excluded_ingredient(recipe, context.excluded_ingredient_ids):
                violations.append(
                    PlanViolation(
                        code=PlannerViolationCode.EXCLUDED_INGREDIENT,
                        slot_id=meal.slot_id,
                    )
                )
            if has_excluded_protein(recipe, context.excluded_protein_sources):
                violations.append(
                    PlanViolation(
                        code=PlannerViolationCode.EXCLUDED_PROTEIN,
                        slot_id=meal.slot_id,
                    )
                )
            if (
                context.max_cooking_time is not None
                and meal.requires_cooking
                and recipe.total_time_minutes > context.max_cooking_time
            ):
                violations.append(
                    PlanViolation(
                        code=PlannerViolationCode.TIME_LIMIT,
                        slot_id=meal.slot_id,
                    )
                )
            if context.allowed_budget_classes is not None:
                allowed = {b.value for b in context.allowed_budget_classes}
                if recipe.budget_class.value not in allowed:
                    violations.append(
                        PlanViolation(
                            code=PlannerViolationCode.BUDGET_CLASS,
                            slot_id=meal.slot_id,
                        )
                    )
            if meal.recipe_id in context.avoided_recipe_ids:
                violations.append(
                    PlanViolation(
                        code=PlannerViolationCode.AVOIDED_RECIPE,
                        slot_id=meal.slot_id,
                    )
                )

            if meal.is_leftover:
                if not context.leftovers_enabled:
                    violations.append(
                        PlanViolation(
                            code=PlannerViolationCode.LEFTOVER_DISABLED,
                            slot_id=meal.slot_id,
                        )
                    )
                if not meal.source_slot_id:
                    violations.append(
                        PlanViolation(
                            code=PlannerViolationCode.ORPHAN_LEFTOVER,
                            slot_id=meal.slot_id,
                        )
                    )
                else:
                    src = by_slot.get(meal.source_slot_id)
                    if src is None:
                        violations.append(
                            PlanViolation(
                                code=PlannerViolationCode.ORPHAN_LEFTOVER,
                                slot_id=meal.slot_id,
                            )
                        )
                    else:
                        if src.recipe_id != meal.recipe_id:
                            violations.append(
                                PlanViolation(
                                    code=PlannerViolationCode.LEFTOVER_RECIPE_MISMATCH,
                                    slot_id=meal.slot_id,
                                )
                            )
                        if slot_order.get(meal.source_slot_id, 10**9) >= slot_order.get(
                            meal.slot_id, -1
                        ):
                            violations.append(
                                PlanViolation(
                                    code=PlannerViolationCode.LEFTOVER_BEFORE_SOURCE,
                                    slot_id=meal.slot_id,
                                )
                            )
                leftover_counts[meal.cooking_instance_id] = (
                    leftover_counts.get(meal.cooking_instance_id, 0) + 1
                )
                inst = inst_by_id.get(meal.cooking_instance_id)
                if inst is None:
                    violations.append(
                        PlanViolation(
                            code=PlannerViolationCode.COOKING_INSTANCE_INCONSISTENT,
                            slot_id=meal.slot_id,
                        )
                    )

            inst = inst_by_id.get(meal.cooking_instance_id)
            if inst is None:
                violations.append(
                    PlanViolation(
                        code=PlannerViolationCode.COOKING_INSTANCE_INCONSISTENT,
                        slot_id=meal.slot_id,
                    )
                )
            elif inst.recipe_id != meal.recipe_id:
                violations.append(
                    PlanViolation(
                        code=PlannerViolationCode.COOKING_INSTANCE_INCONSISTENT,
                        slot_id=meal.slot_id,
                        detail="recipe mismatch",
                    )
                )

        for inst in plan.cooking_instances:
            if inst.servings_consumed > inst.servings_cooked:
                violations.append(
                    PlanViolation(
                        code=PlannerViolationCode.LEFTOVER_OVERCONSUMED,
                        detail=inst.cooking_instance_id,
                    )
                )

        # avoid_consecutive_days across adjacent days (independent cooks)
        cooks_by_day: dict[int, list[str]] = {}
        for meal in plan.meals:
            if meal.is_leftover:
                continue
            cooks_by_day.setdefault(meal.day_index, []).append(meal.recipe_id)
        for day, ids in cooks_by_day.items():
            prev = cooks_by_day.get(day - 1, [])
            for a in ids:
                for b in prev:
                    if relation_index.has_avoid_consecutive(a, b):
                        violations.append(
                            PlanViolation(
                                code=PlannerViolationCode.AVOID_CONSECUTIVE_DAYS,
                                detail=f"{a}<->{b}",
                            )
                        )

        # Independent recipe repeats
        cook_counts: dict[str, int] = {}
        for meal in plan.meals:
            if meal.is_leftover:
                continue
            cook_counts[meal.recipe_id] = cook_counts.get(meal.recipe_id, 0) + 1
        for rid, count in cook_counts.items():
            if count > context.config.max_independent_recipe_repeats:
                violations.append(
                    PlanViolation(
                        code=PlannerViolationCode.RECIPE_REPEAT,
                        detail=f"{rid} x{count}",
                    )
                )

        return ValidationReport(ok=not violations, violations=violations)
