import type { MealType } from '@/types/meal';
import type { DayMeal } from '@/types/menu';

export type CookingStatus =
  | { kind: 'cook'; label: string }
  | { kind: 'leftover'; label: string; sourceLabel?: string }
  | { kind: 'prepared'; label: string }
  | { kind: 'ready'; label: string }
  | { kind: 'unknown'; label?: string };

export type DayCookingOverviewStatus = 'cook' | 'leftovers' | 'no_cook' | 'unknown';

export interface MealReference {
  meal_id: string;
  recipe_name: string;
  day_number: number;
  day_label: string;
  meal_type: MealType;
}

export type MealsByIdIndex = Record<string, MealReference>;

export function mealHasCookingMetadata(meal: DayMeal): boolean {
  return (
    meal.meal_id != null ||
    meal.requires_cooking != null ||
    meal.prepared_on_day != null ||
    meal.uses_leftovers === true ||
    meal.source_meal_id != null
  );
}

export function dayHasCookingMetadata(meals: DayMeal[]): boolean {
  return meals.some(mealHasCookingMetadata);
}
