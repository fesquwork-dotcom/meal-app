import { COOKING_LABELS } from '@/features/menu-plan/cooking/constants';
import { findMealReference } from '@/features/menu-plan/cooking/mealsById';
import type { CookingStatus, MealsByIdIndex } from '@/features/menu-plan/cooking/types';
import { mealHasCookingMetadata } from '@/features/menu-plan/cooking/types';
import type { DayMeal } from '@/types/menu';

export function formatLeftoverSourceLabel(sourceRecipeName: string, sourceDayNumber: number): string {
  return `${COOKING_LABELS.basis}: ${sourceRecipeName}, день ${sourceDayNumber}`;
}

/** Maps structured meal metadata to a user-facing cooking status. */
export function getCookingStatus(
  meal: DayMeal,
  currentDay: number,
  mealsById: MealsByIdIndex,
): CookingStatus {
  if (!mealHasCookingMetadata(meal)) {
    return { kind: 'unknown' };
  }

  if (meal.requires_cooking === true) {
    return { kind: 'cook', label: COOKING_LABELS.cook };
  }

  if (meal.uses_leftovers === true) {
    const source = findMealReference(mealsById, meal.source_meal_id);
    return {
      kind: 'leftover',
      label: COOKING_LABELS.leftover,
      sourceLabel: source
        ? formatLeftoverSourceLabel(source.recipe_name, source.day_number)
        : undefined,
    };
  }

  if (
    meal.requires_cooking === false &&
    meal.prepared_on_day != null &&
    meal.prepared_on_day < currentDay
  ) {
    return { kind: 'prepared', label: COOKING_LABELS.prepared };
  }

  if (meal.requires_cooking === false) {
    return { kind: 'ready', label: COOKING_LABELS.noCook };
  }

  return { kind: 'unknown' };
}
