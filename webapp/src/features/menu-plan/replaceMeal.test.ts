import { describe, expect, it } from 'vitest';

import { canReplaceMeal } from '@/features/menu-plan/canReplaceMeal';
import { wrapForStorage, unwrapFromStorage } from '@/lib/storageVersion';
import type { MenuPlan } from '@/types/menu';

const basePlan: MenuPlan = {
  summary: 'План',
  plan_start_date: '2026-07-13',
  strategy_id: 'strategy-123',
  total_cost: 1000,
  days_plan: [
    {
      day: 'День 1',
      breakfast: 'Овсянка',
      lunch: 'Борщ',
      dinner: 'Рыба',
      meals: [
        {
          type: 'breakfast',
          recipe_name: 'Овсянка',
          meal_id: 'day1_breakfast',
          requires_cooking: true,
          prepared_on_day: 1,
        },
      ],
    },
    {
      day: 'День 2',
      breakfast: 'Сырники',
      lunch: 'Суп',
      dinner: 'Курица',
      meals: [
        {
          type: 'dinner',
          recipe_name: 'Курица',
          meal_id: 'day2_dinner',
          requires_cooking: true,
          prepared_on_day: 2,
        },
      ],
    },
    {
      day: 'День 3',
      breakfast: 'Омлет',
      lunch: 'Плов',
      dinner: 'Рыба',
      meals: [],
    },
  ],
  recipes: [
    {
      name: 'Овсянка',
      emoji: '🥣',
      cook_time: '10 мин',
      kbju: '',
      ingredients: [{ name: 'овсянка', amount: '1' }],
      steps: ['Готовить'],
    },
  ],
  basket: [{ category: 'Крупы', items: [{ name: 'овсянка', weight: '1 кг', price: 1000 }] }],
};

describe('canReplaceMeal', () => {
  it('allows replacement for strategy-aware active plan', () => {
    expect(
      canReplaceMeal(basePlan, new Date(2026, 6, 14)),
    ).toBe(true);
  });

  it('disables replacement for legacy plan without strategy_id', () => {
    expect(canReplaceMeal({ ...basePlan, strategy_id: undefined })).toBe(false);
  });

  it('disables replacement for completed plan', () => {
    expect(
      canReplaceMeal(basePlan, new Date(2026, 6, 20)),
    ).toBe(false);
  });
});

describe('replace meal localStorage round-trip', () => {
  it('preserves strategy_id after replacement success payload', () => {
    const updated: MenuPlan = {
      ...basePlan,
      days_plan: [
        {
          ...basePlan.days_plan[0],
          meals: [
            {
              type: 'breakfast',
              recipe_name: 'Сырники',
              meal_id: 'day1_breakfast',
              requires_cooking: true,
              prepared_on_day: 1,
            },
          ],
        },
      ],
    };

    const stored = wrapForStorage(updated);
    const loaded = unwrapFromStorage<MenuPlan>(stored);
    expect(loaded?.strategy_id).toBe('strategy-123');
    expect(loaded?.plan_start_date).toBe('2026-07-13');
    expect(loaded?.days_plan[0].meals[0].meal_id).toBe('day1_breakfast');
  });
});
