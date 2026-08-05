"""Deterministic weekly meal slot construction."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from recipes.enums import MealType
from recipes.planning.context import WeeklyPlanningContext


class WeeklyMealSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    day_index: int = Field(ge=1)
    meal_type: MealType
    slot_id: str
    requires_recipe: bool = True
    is_cook_day: bool = True
    leftovers_allowed: bool = False
    order_index: int = 0


def make_slot_id(day_index: int, meal_type: MealType | str) -> str:
    mt = meal_type.value if isinstance(meal_type, MealType) else str(meal_type)
    return f"day{day_index}_{mt}"


def build_weekly_slots(context: WeeklyPlanningContext) -> list[WeeklyMealSlot]:
    """Build stable ordered slots: day-major, meal_types order as given."""
    slots: list[WeeklyMealSlot] = []
    order = 0
    for day in range(1, context.days + 1):
        is_cook = context.is_cook_day(day)
        for meal_type in context.meal_types:
            slots.append(
                WeeklyMealSlot(
                    day_index=day,
                    meal_type=meal_type,
                    slot_id=make_slot_id(day, meal_type),
                    requires_recipe=True,
                    is_cook_day=is_cook,
                    leftovers_allowed=context.leftovers_enabled,
                    order_index=order,
                )
            )
            order += 1
    return slots
