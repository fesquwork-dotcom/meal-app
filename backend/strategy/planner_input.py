"""Adapter between WeeklyStrategy and the menu generation planner."""

from __future__ import annotations

from dataclasses import dataclass

from strategy.models import WeeklyStrategy


@dataclass(frozen=True)
class PlannerInput:
    """Operational request fields plus resolved strategic constraints for the planner."""

    budget: float
    days: int
    meal_types: list[str]
    meals_per_day: int
    persons: int
    proteins: list[str]
    goal: str
    cooktime: str
    allergies: str
    store: str
    strategy: WeeklyStrategy

    def as_generate_menu_kwargs(self) -> dict[str, object]:
        return {
            "budget": self.budget,
            "days": self.days,
            "meal_types": self.meal_types,
            "meals_per_day": self.meals_per_day,
            "persons": self.persons,
            "proteins": self.proteins,
            "goal": self.goal,
            "cooktime": self.cooktime,
            "allergies": self.allergies,
            "store": self.store,
            "strategy": self.strategy,
        }


def build_planner_input(
    *,
    strategy: WeeklyStrategy,
    persons: int,
    proteins: list[str],
    cooktime: str,
    allergies: str,
    store: str,
) -> PlannerInput:
    """Maps validated strategy and operational request fields into planner input."""
    return PlannerInput(
        budget=strategy.budget,
        days=strategy.days,
        meal_types=list(strategy.meal_types),
        meals_per_day=strategy.meals_per_day,
        persons=persons,
        proteins=proteins,
        goal=strategy.goal,
        cooktime=cooktime,
        allergies=allergies,
        store=store,
        strategy=strategy,
    )
