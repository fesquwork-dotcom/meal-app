import { describe, expect, it, vi } from 'vitest';
import { calculateMealProgress } from '@/features/positive-events/mealProgress';
import type { DayPlan } from '@/types/menu';

function day(dayNumber: number, mealIds: string[]): DayPlan {
  return {
    day: `День ${dayNumber}`,
    breakfast: '',
    lunch: '',
    dinner: '',
    meals: mealIds.map((mealId, index) => ({
      type: index === 0 ? 'breakfast' : index === 1 ? 'lunch' : 'dinner',
      recipe_name: `Блюдо ${mealId}`,
      meal_id: mealId,
    })),
  };
}

describe('meal progress', () => {
  it('calculates absolute day progress', () => {
    const isMarked = vi.fn((type: string, mealId?: string | null) =>
      type === 'meal_cooked' && mealId === 'd1-breakfast',
    );
    expect(calculateMealProgress([day(1, ['d1-breakfast', 'd1-lunch', 'd1-dinner'])], { isMarked }))
      .toEqual({ cooked: 1, total: 3, complete: false });
  });

  it('calculates complete week without percentages', () => {
    const days = [day(1, ['d1-breakfast', 'd1-dinner']), day(2, ['d2-breakfast'])];
    const isMarked = vi.fn((type: string) => type === 'meal_cooked');
    expect(calculateMealProgress(days, { isMarked })).toEqual({
      cooked: 3,
      total: 3,
      complete: true,
    });
  });

  it('ignores legacy meals without meal_id because they cannot be marked', () => {
    const legacy = day(1, ['d1-breakfast']);
    legacy.meals.push({ type: 'dinner', recipe_name: 'Legacy' });
    expect(calculateMealProgress([legacy], { isMarked: () => false })).toEqual({
      cooked: 0,
      total: 1,
      complete: false,
    });
  });
});
