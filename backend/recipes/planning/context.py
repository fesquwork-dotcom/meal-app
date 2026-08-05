"""WeeklyPlanningContext — normalized source of truth for the planner."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from recipes.enums import BudgetClass, GoalType, MealType, ProteinSourceTag
from recipes.planning.weights import (
    DEFAULT_PLANNER_CONFIG,
    DEFAULT_WEEKLY_WEIGHTS,
    WeeklyPlannerConfig,
    WeeklyPlannerWeights,
)
from recipes.quality.enums import QualityStatus
from recipes.selection.profile_adapter import (
    PROFILE_GOAL_TO_CATALOG,
    PROFILE_PROTEIN_TO_TAG,
    budget_float_to_classes,
)
from strategy.context import ProfileContext
from strategy.models import WeeklyStrategy
from strategy.resolvers import BATCH_COOK_GOALS


class WeeklyPlanningContext(BaseModel):
    """Normalized week-level planning requirements.

    Built once from Profile + WeeklyStrategy; Planner must not re-read raw profile.
    """

    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    days: int = Field(ge=1, le=14)
    meal_types: list[MealType]
    goal: GoalType | None = None
    allowed_budget_classes: list[BudgetClass] | None = None
    max_cooking_time: int | None = Field(default=None, ge=1)
    preferred_proteins: set[ProteinSourceTag] = Field(default_factory=set)
    excluded_ingredient_ids: set[str] = Field(default_factory=set)
    excluded_protein_sources: set[ProteinSourceTag] = Field(default_factory=set)
    required_tags: set[tuple[str, str]] = Field(default_factory=set)
    excluded_tags: set[tuple[str, str]] = Field(default_factory=set)
    leftovers_enabled: bool = False
    cook_days: list[int] = Field(default_factory=list)
    shopping_days: list[int] = Field(default_factory=list)
    prefer_faster_meals: bool = False
    family_mode: bool = False
    prefer_batch_friendly: bool = False
    minimum_quality_status: QualityStatus | None = None
    avoided_recipe_ids: set[str] = Field(default_factory=set)
    recent_recipe_ids: set[str] = Field(default_factory=set)
    strategy_id: str | None = None
    strategy_goal_raw: str | None = None
    config: WeeklyPlannerConfig = Field(default_factory=lambda: DEFAULT_PLANNER_CONFIG)
    weights: WeeklyPlannerWeights = Field(default_factory=lambda: DEFAULT_WEEKLY_WEIGHTS)

    @field_validator("meal_types", mode="before")
    @classmethod
    def _coerce_meals(cls, value: object) -> object:
        if isinstance(value, (list, tuple)):
            return [MealType(str(v)) for v in value]
        return value

    @field_validator(
        "preferred_proteins",
        "excluded_protein_sources",
        mode="before",
    )
    @classmethod
    def _coerce_proteins(cls, value: object) -> object:
        if value is None:
            return set()
        if isinstance(value, (list, tuple, set, frozenset)):
            return {ProteinSourceTag(str(v)) for v in value}
        return value

    @field_validator(
        "excluded_ingredient_ids",
        "avoided_recipe_ids",
        "recent_recipe_ids",
        mode="before",
    )
    @classmethod
    def _coerce_str_set(cls, value: object) -> object:
        if value is None:
            return set()
        if isinstance(value, (list, tuple, set, frozenset)):
            return {str(v) for v in value}
        return value

    def is_cook_day(self, day_index: int) -> bool:
        if not self.cook_days:
            return True
        return day_index in self.cook_days

    def fingerprint(self) -> dict[str, Any]:
        return {
            "days": self.days,
            "meal_types": [m.value for m in self.meal_types],
            "goal": self.goal.value if self.goal else None,
            "allowed_budget_classes": (
                [b.value for b in self.allowed_budget_classes]
                if self.allowed_budget_classes
                else None
            ),
            "max_cooking_time": self.max_cooking_time,
            "preferred_proteins": sorted(p.value for p in self.preferred_proteins),
            "excluded_ingredient_ids": sorted(self.excluded_ingredient_ids),
            "excluded_protein_sources": sorted(
                p.value for p in self.excluded_protein_sources
            ),
            "leftovers_enabled": self.leftovers_enabled,
            "cook_days": list(self.cook_days),
            "prefer_faster_meals": self.prefer_faster_meals,
            "family_mode": self.family_mode,
            "prefer_batch_friendly": self.prefer_batch_friendly,
            "minimum_quality_status": (
                self.minimum_quality_status.value
                if self.minimum_quality_status
                else None
            ),
            "avoided_recipe_ids": sorted(self.avoided_recipe_ids),
            "candidate_pool_size": self.config.candidate_pool_size,
            "beam_width": self.config.beam_width,
            "max_independent_recipe_repeats": self.config.max_independent_recipe_repeats,
        }


def build_planning_context_from_strategy(
    strategy: WeeklyStrategy,
    *,
    excluded_ingredient_ids: set[str] | None = None,
    excluded_protein_sources: set[ProteinSourceTag] | None = None,
    avoided_recipe_ids: set[str] | None = None,
    recent_recipe_ids: set[str] | None = None,
    minimum_quality_status: QualityStatus | None = None,
    config: WeeklyPlannerConfig | None = None,
    weights: WeeklyPlannerWeights | None = None,
    strategy_id: str | None = None,
    max_cooking_time_override: int | None = None,
    allowed_budget_override: list[BudgetClass] | None = None,
    leftovers_override: bool | None = None,
    goal_override: GoalType | None = None,
) -> WeeklyPlanningContext:
    """Adapt WeeklyStrategy into WeeklyPlanningContext (single source of truth)."""
    meal_types = [MealType(m) for m in strategy.meal_types if m != "snack"]
    if not meal_types:
        meal_types = [MealType.BREAKFAST, MealType.LUNCH, MealType.DINNER]

    preferred: set[ProteinSourceTag] = set()
    for protein in strategy.preferred_proteins:
        if protein == "any":
            preferred = set()
            break
        mapped = PROFILE_PROTEIN_TO_TAG.get(protein)
        if mapped:
            preferred.add(mapped)

    prefer_batch = strategy.goal in BATCH_COOK_GOALS or (
        len(strategy.cook_days) < strategy.days
    )

    max_time = max_cooking_time_override
    if max_time is None:
        max_time = strategy.cooking_time_limit
        if strategy.prefer_faster_meals and max_time:
            max_time = min(max_time, 30)

    return WeeklyPlanningContext(
        days=strategy.days,
        meal_types=meal_types,
        goal=goal_override or PROFILE_GOAL_TO_CATALOG.get(strategy.goal),
        allowed_budget_classes=allowed_budget_override
        or budget_float_to_classes(strategy.budget),
        max_cooking_time=max_time,
        preferred_proteins=preferred,
        excluded_ingredient_ids=excluded_ingredient_ids or set(),
        excluded_protein_sources=excluded_protein_sources or set(),
        leftovers_enabled=(
            strategy.leftovers_enabled if leftovers_override is None else leftovers_override
        ),
        cook_days=list(strategy.cook_days),
        shopping_days=list(strategy.shopping_days),
        prefer_faster_meals=strategy.prefer_faster_meals,
        family_mode=strategy.goal == "home",
        prefer_batch_friendly=prefer_batch,
        minimum_quality_status=minimum_quality_status,
        avoided_recipe_ids=avoided_recipe_ids or set(),
        recent_recipe_ids=recent_recipe_ids or set(),
        strategy_id=strategy_id,
        strategy_goal_raw=strategy.goal,
        config=config or DEFAULT_PLANNER_CONFIG,
        weights=weights or DEFAULT_WEEKLY_WEIGHTS,
    )


def build_planning_context_from_profile(
    profile: ProfileContext | dict[str, Any],
    *,
    days: int | None = None,
    meal_types: list[MealType] | None = None,
    leftovers_enabled: bool = True,
    cook_days: list[int] | None = None,
    **kwargs: Any,
) -> WeeklyPlanningContext:
    """Lightweight profile-only context when no WeeklyStrategy is available."""
    if isinstance(profile, dict):
        ctx = ProfileContext.from_profile(profile)
    else:
        ctx = profile

    n_days = days or ctx.days or 7
    meals = meal_types or [MealType(m) for m in (ctx.meal_types or ["breakfast", "lunch", "dinner"])]
    preferred: set[ProteinSourceTag] = set()
    for protein in ctx.proteins or []:
        if protein == "any":
            preferred = set()
            break
        mapped = PROFILE_PROTEIN_TO_TAG.get(protein)
        if mapped:
            preferred.add(mapped)

    cook = cook_days
    if cook is None:
        cook = list(range(1, n_days + 1))

    return WeeklyPlanningContext(
        days=n_days,
        meal_types=meals,
        goal=PROFILE_GOAL_TO_CATALOG.get(ctx.goal),
        allowed_budget_classes=budget_float_to_classes(float(ctx.budget or 3000)),
        max_cooking_time=kwargs.get("max_cooking_time"),
        preferred_proteins=preferred,
        leftovers_enabled=leftovers_enabled,
        cook_days=cook,
        shopping_days=[1],
        prefer_faster_meals=bool(kwargs.get("prefer_faster_meals", False)),
        family_mode=ctx.goal == "home",
        minimum_quality_status=kwargs.get("minimum_quality_status"),
        avoided_recipe_ids=set(kwargs.get("avoided_recipe_ids") or []),
        excluded_protein_sources=set(kwargs.get("excluded_protein_sources") or []),
        excluded_ingredient_ids=set(kwargs.get("excluded_ingredient_ids") or []),
        config=kwargs.get("config") or DEFAULT_PLANNER_CONFIG,
        weights=kwargs.get("weights") or DEFAULT_WEEKLY_WEIGHTS,
    )
