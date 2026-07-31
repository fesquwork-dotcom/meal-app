import { describe, expect, it } from 'vitest';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';

describe('normalizeMenuPlan meal_types', () => {
  it('converts legacy DayPlan to meals[]', () => {
    const plan = normalizeMenuPlan({
      summary: 'План',
      total_cost: 1000,
      days_plan: [
        {
          day: 'День 1',
          breakfast: 'Овсянка',
          lunch: 'Борщ',
          dinner: 'Рыба',
        },
      ],
      recipes: [{ name: 'Овсянка', emoji: '🥣', ingredients: [{ name: 'овсянка', amount: '1' }], steps: ['Готовить'] }],
      basket: [{ category: 'Крупы', items: [{ name: 'овсянка', weight: '1 кг', price: 1000 }] }],
    });

    expect(plan?.days_plan[0].meals).toEqual([
      { type: 'breakfast', recipe_name: 'Овсянка', uses_leftovers: false },
      { type: 'lunch', recipe_name: 'Борщ', uses_leftovers: false },
      { type: 'dinner', recipe_name: 'Рыба', uses_leftovers: false },
    ]);
  });

  it('preserves new meals[] format', () => {
    const plan = normalizeMenuPlan({
      summary: 'План',
      total_cost: 500,
      days_plan: [
        {
          day: 'День 1',
          meals: [
            { type: 'breakfast', recipe_name: 'Овсянка' },
            { type: 'dinner', recipe_name: 'Рыба' },
          ],
        },
      ],
      recipes: [{ name: 'Овсянка', emoji: '🥣', ingredients: [{ name: 'овсянка', amount: '1' }], steps: ['Готовить'] }],
      basket: [{ category: 'Крупы', items: [{ name: 'овсянка', weight: '1 кг', price: 500 }] }],
    });

    expect(plan?.days_plan[0].meals).toEqual([
      { type: 'breakfast', recipe_name: 'Овсянка', uses_leftovers: false },
      { type: 'dinner', recipe_name: 'Рыба', uses_leftovers: false },
    ]);
  });

  it('supports snack meals', () => {
    const plan = normalizeMenuPlan({
      summary: 'План',
      total_cost: 200,
      days_plan: [
        {
          day: 'День 1',
          meals: [{ type: 'snack', recipe_name: 'Йогурт' }],
        },
      ],
      recipes: [{ name: 'Йогурт', emoji: '🥛', ingredients: [{ name: 'йогурт', amount: '1' }], steps: ['Подать'] }],
      basket: [{ category: 'Молочное', items: [{ name: 'йогурт', weight: '1 шт', price: 200 }] }],
    });

    expect(plan?.days_plan[0].meals[0]).toEqual({ type: 'snack', recipe_name: 'Йогурт', uses_leftovers: false });
  });

  it('deduplicates duplicate meal types in meals[]', () => {
    const plan = normalizeMenuPlan({
      summary: 'План',
      total_cost: 200,
      days_plan: [
        {
          day: 'День 1',
          meals: [
            { type: 'breakfast', recipe_name: 'Овсянка' },
            { type: 'breakfast', recipe_name: 'Сырники' },
          ],
        },
      ],
      recipes: [{ name: 'Овсянка', emoji: '🥣', ingredients: [{ name: 'овсянка', amount: '1' }], steps: ['Готовить'] }],
      basket: [{ category: 'Крупы', items: [{ name: 'овсянка', weight: '1 кг', price: 200 }] }],
    });

    expect(plan?.days_plan[0].meals).toHaveLength(1);
    expect(plan?.days_plan[0].meals[0].recipe_name).toBe('Овсянка');
  });

  it('ignores unknown meal types without throwing', () => {
    const plan = normalizeMenuPlan({
      summary: 'План',
      total_cost: 200,
      days_plan: [
        {
          day: 'День 1',
          meals: [
            { type: 'brunch', recipe_name: 'Омлет' },
            { type: 'dinner', recipe_name: 'Рыба' },
          ],
        },
      ],
      recipes: [{ name: 'Рыба', emoji: '🐟', ingredients: [{ name: 'рыба', amount: '1' }], steps: ['Готовить'] }],
      basket: [{ category: 'Рыба', items: [{ name: 'рыба', weight: '1 кг', price: 200 }] }],
    });

    expect(plan?.days_plan[0].meals).toEqual([{ type: 'dinner', recipe_name: 'Рыба', uses_leftovers: false }]);
  });
});
