import { describe, expect, it } from 'vitest';
import { getMenuPlanFingerprint } from '@/features/menu-plan/menuPlanFingerprint';
import type { MenuPlan } from '@/types/menu';

const basePlan: MenuPlan = {
  summary: 'Неделя домашней еды',
  total_cost: 3500,
  days_plan: [
    {
      day: 'День 1',
      meals: [
        { type: 'breakfast', recipe_name: 'Овсянка' },
        { type: 'lunch', recipe_name: 'Суп' },
        { type: 'dinner', recipe_name: 'Гречка' },
      ],
      breakfast: 'Овсянка',
      lunch: 'Суп',
      dinner: 'Гречка',
    },
  ],
  recipes: [],
  basket: [
    {
      category: 'Крупы',
      items: [{ name: 'Гречка', weight: '500 г', price: 120 }],
    },
  ],
};

describe('getMenuPlanFingerprint', () => {
  it('returns the same fingerprint for identical plans', () => {
    const clone: MenuPlan = structuredClone(basePlan);
    expect(getMenuPlanFingerprint(basePlan)).toBe(getMenuPlanFingerprint(clone));
  });

  it('changes fingerprint when basket changes', () => {
    const changed: MenuPlan = {
      ...basePlan,
      basket: [
        {
          category: 'Крупы',
          items: [{ name: 'Рис', weight: '500 г', price: 90 }],
        },
      ],
    };

    expect(getMenuPlanFingerprint(changed)).not.toBe(getMenuPlanFingerprint(basePlan));
  });

  it('changes fingerprint when days_plan changes', () => {
    const changed: MenuPlan = {
      ...basePlan,
      days_plan: [
        {
          day: 'День 1',
          meals: [
            { type: 'breakfast', recipe_name: 'Овсянка' },
            { type: 'lunch', recipe_name: 'Суп' },
            { type: 'dinner', recipe_name: 'Паста' },
          ],
          breakfast: 'Овсянка',
          lunch: 'Суп',
          dinner: 'Паста',
        },
      ],
    };

    expect(getMenuPlanFingerprint(changed)).not.toBe(getMenuPlanFingerprint(basePlan));
  });
});
