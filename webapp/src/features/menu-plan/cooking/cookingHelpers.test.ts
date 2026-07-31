import { describe, expect, it } from 'vitest';
import {
  getDayCookingOverviewStatus,
  getDayCookingSummary,
} from '@/features/menu-plan/cooking/dayCookingSummary';
import { buildMealsByIdIndex } from '@/features/menu-plan/cooking/mealsById';
import type { DayMeal, MenuPlan } from '@/types/menu';

describe('day cooking helpers', () => {
  it('classifies cook day overview', () => {
    const meals: DayMeal[] = [
      { type: 'breakfast', recipe_name: 'Овсянка', requires_cooking: false, uses_leftovers: false },
      { type: 'dinner', recipe_name: 'Курица', requires_cooking: true, uses_leftovers: false, meal_id: 'd1' },
    ];

    expect(getDayCookingOverviewStatus(meals)).toBe('cook');
  });

  it('classifies leftovers day overview', () => {
    const meals: DayMeal[] = [
      {
        type: 'lunch',
        recipe_name: 'Боул',
        requires_cooking: false,
        uses_leftovers: true,
        source_meal_id: 'd1',
      },
    ];

    expect(getDayCookingOverviewStatus(meals)).toBe('leftovers');
  });

  it('returns unknown for legacy day', () => {
    expect(
      getDayCookingOverviewStatus([{ type: 'dinner', recipe_name: 'Омлет', uses_leftovers: false }]),
    ).toBe('unknown');
  });

  it('summarizes cook count for today', () => {
    const summary = getDayCookingSummary([
      { type: 'lunch', recipe_name: 'Суп', requires_cooking: true, uses_leftovers: false },
      { type: 'dinner', recipe_name: 'Рыба', requires_cooking: true, uses_leftovers: false },
    ]);

    expect(summary?.text).toBe('Сегодня готовим: 2 блюда');
    expect(summary?.cookCount).toBe(2);
  });

  it('builds mealsById index once and resolves source', () => {
    const menu: MenuPlan = {
      summary: 'План',
      total_cost: 1000,
      days_plan: [
        {
          day: 'День 1',
          meals: [
            {
              type: 'dinner',
              recipe_name: 'Курица',
              meal_id: 'day1_dinner',
              requires_cooking: true,
              uses_leftovers: false,
            },
          ],
          breakfast: '',
          lunch: '',
          dinner: 'Курица',
        },
      ],
      recipes: [],
      basket: [],
    };

    const index = buildMealsByIdIndex(menu);

    expect(index.day1_dinner).toMatchObject({
      recipe_name: 'Курица',
      day_number: 1,
    });
  });

  it('ignores duplicate meal_id safely', () => {
    const menu: MenuPlan = {
      summary: 'План',
      total_cost: 1000,
      days_plan: [
        {
          day: 'День 1',
          meals: [
            { type: 'lunch', recipe_name: 'A', meal_id: 'dup', uses_leftovers: false },
            { type: 'dinner', recipe_name: 'B', meal_id: 'dup', uses_leftovers: false },
          ],
          breakfast: '',
          lunch: 'A',
          dinner: 'B',
        },
      ],
      recipes: [],
      basket: [],
    };

    const index = buildMealsByIdIndex(menu);

    expect(index.dup.recipe_name).toBe('A');
    expect(Object.keys(index)).toHaveLength(1);
  });
});
