"""Weekly planner scoring weights (independent of Selector weights)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WeeklyPlannerWeights:
    """Weights for weekly score components (normalized contribution shares)."""

    selector_quality: float = 0.35
    recipe_diversity: float = 0.12
    protein_diversity: float = 0.14
    relation_score: float = 0.10
    strategy_alignment: float = 0.12
    batch_efficiency: float = 0.08
    ingredient_reuse: float = 0.05
    # Cap absolute ingredient reuse contribution before weighting.
    ingredient_reuse_cap: float = 0.70
    # Soft penalties (subtracted after weighted sum, clamped).
    recipe_repeat_penalty: float = 0.35
    consecutive_protein_penalty: float = 0.08
    similar_meal_penalty: float = 0.06
    cook_day_miss_penalty: float = 0.04
    # Breakfast softens protein/recipe diversity penalties.
    breakfast_diversity_scale: float = 0.35


DEFAULT_WEEKLY_WEIGHTS = WeeklyPlannerWeights()


@dataclass(frozen=True)
class WeeklyPlannerConfig:
    candidate_pool_size: int = 15
    beam_width: int = 8
    max_states: int = 4000
    max_independent_recipe_repeats: int = 1
    # Max leftover meals consumable from one cooking instance (v1).
    max_leftovers_per_cook: int = 1
    # Prefer leftovers on non-cook days when leftovers_enabled.
    prefer_leftovers_on_non_cook_days: bool = True
    # Allow cooking outside cook_days only if otherwise unfilled (soft escape).
    allow_cook_day_miss: bool = True


DEFAULT_PLANNER_CONFIG = WeeklyPlannerConfig()
