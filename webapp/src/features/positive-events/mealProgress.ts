import type { PositiveEventsApi } from '@/features/positive-events/usePositiveEvents';
import type { DayPlan } from '@/types/menu';

export interface MealProgress {
  cooked: number;
  total: number;
  complete: boolean;
}

export function calculateMealProgress(
  days: DayPlan[],
  events: Pick<PositiveEventsApi, 'isMarked'>,
): MealProgress {
  let cooked = 0;
  let total = 0;

  for (const day of days) {
    for (const meal of day.meals ?? []) {
      if (!meal.meal_id) {
        continue;
      }
      total += 1;
      if (events.isMarked('meal_cooked', meal.meal_id)) {
        cooked += 1;
      }
    }
  }

  return {
    cooked,
    total,
    complete: total > 0 && cooked === total,
  };
}
