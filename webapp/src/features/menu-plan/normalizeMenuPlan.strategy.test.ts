import { describe, expect, it } from 'vitest';

import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';
import { wrapForStorage, unwrapFromStorage } from '@/lib/storageVersion';

const basePlan = {
  summary: 'План',
  total_cost: 1000,
  days_plan: [
    {
      day: 'День 1',
      meals: [{ type: 'breakfast', recipe_name: 'Овсянка' }],
    },
  ],
  recipes: [
    {
      name: 'Овсянка',
      emoji: '🥣',
      ingredients: [{ name: 'овсянка', amount: '1' }],
      steps: ['Готовить'],
    },
  ],
  basket: [{ category: 'Крупы', items: [{ name: 'овсянка', weight: '1 кг', price: 1000 }] }],
};

describe('normalizeMenuPlan strategy_id', () => {
  it('preserves strategy_id from API payload', () => {
    const plan = normalizeMenuPlan({
      ...basePlan,
      strategy_id: '550e8400-e29b-41d4-a716-446655440000',
    });

    expect(plan?.strategy_id).toBe('550e8400-e29b-41d4-a716-446655440000');
  });

  it('drops empty strategy_id', () => {
    const plan = normalizeMenuPlan({
      ...basePlan,
      strategy_id: '   ',
    });

    expect(plan?.strategy_id).toBeUndefined();
  });

  it('supports legacy menu without strategy_id', () => {
    const plan = normalizeMenuPlan(basePlan);
    expect(plan?.strategy_id).toBeUndefined();
  });

  it('round-trips strategy_id through localStorage with calendar metadata', () => {
    const normalized = normalizeMenuPlan({
      ...basePlan,
      plan_start_date: '2026-07-13',
      strategy_id: 'strategy-abc-123',
      days_plan: [
        {
          day: 'День 1',
          meals: [
            {
              type: 'breakfast',
              recipe_name: 'Овсянка',
              meal_id: 'd1-breakfast',
              requires_cooking: true,
              prepared_on_day: 1,
            },
          ],
        },
      ],
    });

    const stored = wrapForStorage(normalized);
    const loaded = unwrapFromStorage<unknown>(stored);
    const roundTripped = normalizeMenuPlan(loaded);

    expect(roundTripped?.strategy_id).toBe('strategy-abc-123');
    expect(roundTripped?.plan_start_date).toBe('2026-07-13');
    expect(roundTripped?.days_plan[0].meals[0].meal_id).toBe('d1-breakfast');
  });
});
