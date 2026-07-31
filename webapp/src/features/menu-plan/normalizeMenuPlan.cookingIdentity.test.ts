import { describe, expect, it } from 'vitest';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';

describe('cooking instance normalization', () => {
  it('preserves cooking_instance_id through normalization', () => {
    const plan = normalizeMenuPlan({
      summary: 'Тест',
      total_cost: 100,
      days_plan: [
        {
          day: 'День 1',
          meals: [
            {
              type: 'dinner',
              recipe_name: 'Курица',
              recipe_id: 'recipe_day1_dinner',
              cooking_instance_id: 'batch_chicken_day1',
              meal_id: 'day1_dinner',
            },
          ],
        },
      ],
      recipes: [
        {
          recipe_id: 'recipe_day1_dinner',
          name: 'Курица',
          ingredients: [{ name: 'Курица', amount: '500 г', contribution: 'purchase' }],
          steps: ['Готовить'],
        },
      ],
      basket: [{ category: 'Продукты', items: [{ name: 'Курица', weight: '500 г', price: 100 }] }],
    });

    expect(plan?.days_plan[0].meals[0].cooking_instance_id).toBe('batch_chicken_day1');
  });

  it('drops empty cooking_instance_id', () => {
    const plan = normalizeMenuPlan({
      summary: 'Тест',
      total_cost: 0,
      days_plan: [
        {
          day: 'День 1',
          meals: [{ type: 'lunch', recipe_name: 'Суп', cooking_instance_id: '   ' }],
        },
      ],
      recipes: [
        { name: 'Суп', ingredients: [{ name: 'Вода', amount: '1 л' }], steps: ['Варить'] },
      ],
      basket: [{ category: 'Продукты', items: [{ name: 'Вода', weight: '1 л', price: 0 }] }],
    });

    expect(plan?.days_plan[0].meals[0].cooking_instance_id).toBeNull();
  });

  it('round-trips cooking_instance_id via JSON', () => {
    const input = {
      summary: 'Тест',
      total_cost: 0,
      days_plan: [
        {
          day: 'День 1',
          meals: [
            {
              type: 'breakfast',
              recipe_name: 'Овсянка',
              cooking_instance_id: 'cook_day1_breakfast',
            },
          ],
        },
      ],
      recipes: [
        { name: 'Овсянка', ingredients: [{ name: 'Овсянка', amount: '100 г' }], steps: ['Варить'] },
      ],
      basket: [{ category: 'Продукты', items: [{ name: 'Овсянка', weight: '100 г', price: 0 }] }],
    };

    const plan = normalizeMenuPlan(JSON.parse(JSON.stringify(input)));
    expect(plan?.days_plan[0].meals[0].cooking_instance_id).toBe('cook_day1_breakfast');
  });
});
