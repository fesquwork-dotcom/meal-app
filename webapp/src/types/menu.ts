import type { MealType } from '@/types/meal';
import type { BasketCategory, BasketCategoryApiRecord } from '@/types/basket';
import type { Recipe, RecipeApiRecord } from '@/types/recipe';

export interface DayMeal {
  type: MealType;
  recipe_name: string;
  recipe_id?: string | null;
  cooking_instance_id?: string | null;
  meal_id?: string | null;
  requires_cooking?: boolean | null;
  prepared_on_day?: number | null;
  uses_leftovers?: boolean;
  source_meal_id?: string | null;
}

export interface DayMealApiRecord {
  type?: string;
  recipe_name?: string;
  recipe_id?: string | null;
  cooking_instance_id?: string | null;
  meal_id?: string | null;
  requires_cooking?: boolean | null;
  prepared_on_day?: number | null;
  uses_leftovers?: boolean;
  source_meal_id?: string | null;
}

/** Single day in the weekly meal plan. */
export interface DayPlan {
  day: string;
  meals: DayMeal[];
  breakfast: string;
  lunch: string;
  dinner: string;
}

/** Raw day plan as returned by Claude (may omit fields). */
export interface DayPlanApiRecord {
  day?: string;
  meals?: DayMealApiRecord[];
  breakfast?: string;
  lunch?: string;
  dinner?: string;
}

/** Raw response body from POST /api/generate-menu (returned directly, not wrapped). */
export interface MenuPlanApiRecord {
  summary?: string;
  plan_start_date?: string | null;
  strategy_id?: string | null;
  /** Sprint 7.2 — durable server-side plan identity. Absent for legacy plans. */
  menu_plan_id?: string | null;
  menu_plan_revision?: number | null;
  total_cost?: number;
  /** Sprint 10.5.4 — optional dual-cost / utilization fields (backward compatible). */
  budget_limit?: number | null;
  recipe_cost?: number | null;
  shopping_cost?: number | null;
  budget_usage_percent?: number | null;
  days_plan?: DayPlanApiRecord[];
  recipes?: RecipeApiRecord[];
  basket?: BasketCategoryApiRecord[];
  /** Sprint 10.11+ — catalog planner metadata (absent on legacy Claude plans). */
  generation_engine?: string | null;
  planner_score?: number | null;
  planner_version?: string | null;
  planning_duration_ms?: number | null;
}

/** Normalized menu plan used across the app. */
export interface MenuPlan {
  summary: string;
  plan_start_date?: string | null;
  strategy_id?: string | null;
  /**
   * Sprint 7.2 — durable server-side identity. Present only for plans
   * persisted by the backend; legacy localStorage plans have neither.
   */
  menu_plan_id?: string | null;
  menu_plan_revision?: number | null;
  total_cost: number;
  /** Sprint 10.5.4 — present when backend attached utilization after basket rebuild. */
  budget_limit?: number | null;
  recipe_cost?: number | null;
  shopping_cost?: number | null;
  budget_usage_percent?: number | null;
  days_plan: DayPlan[];
  recipes: Recipe[];
  basket: BasketCategory[];
  /** Sprint 10.11+ — catalog planner metadata (absent on legacy Claude plans). */
  generation_engine?: string | null;
  planner_score?: number | null;
  planner_version?: string | null;
  planning_duration_ms?: number | null;
}
