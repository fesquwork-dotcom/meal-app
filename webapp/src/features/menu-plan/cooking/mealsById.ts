import type { MenuPlan } from '@/types/menu';
import type { MealReference, MealsByIdIndex } from '@/features/menu-plan/cooking/types';

/** Builds a meal_id index once per menu plan render cycle. */
export function buildMealsByIdIndex(menuPlan: MenuPlan): MealsByIdIndex {
  const index: MealsByIdIndex = {};

  for (let dayIndex = 0; dayIndex < menuPlan.days_plan.length; dayIndex += 1) {
    const day = menuPlan.days_plan[dayIndex];
    const dayNumber = dayIndex + 1;

    for (const meal of day.meals) {
      const mealId = meal.meal_id?.trim();
      if (!mealId || index[mealId]) {
        continue;
      }

      index[mealId] = {
        meal_id: mealId,
        recipe_name: meal.recipe_name,
        day_number: dayNumber,
        day_label: day.day,
        meal_type: meal.type,
      };
    }
  }

  return index;
}

export function findMealReference(
  mealsById: MealsByIdIndex,
  mealId: string | null | undefined,
): MealReference | undefined {
  if (!mealId) {
    return undefined;
  }

  return mealsById[mealId.trim()];
}
