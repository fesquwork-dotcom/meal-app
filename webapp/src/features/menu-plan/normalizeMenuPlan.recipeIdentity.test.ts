import { describe, expect, it } from 'vitest';
import { matchRecipeForMeal, findRecipeIndexById } from '@/features/menu-plan/matchRecipe';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';
import type { Recipe } from '@/types/recipe';

describe('recipe identity normalization', () => {
  it('preserves recipe_id and contribution through normalization', () => {
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
              meal_id: 'day1_dinner',
            },
          ],
        },
      ],
      recipes: [
        {
          recipe_id: 'recipe_day1_dinner',
          name: 'Курица',
          ingredients: [
            { name: 'Курица', amount: '500 г', contribution: 'purchase' },
            { name: 'Соль', amount: 'по вкусу', contribution: 'pantry' },
          ],
          steps: ['Готовить'],
        },
      ],
      basket: [{ category: 'Продукты', items: [{ name: 'Курица', weight: '500 г', price: 100 }] }],
    });

    expect(plan?.days_plan[0].meals[0].recipe_id).toBe('recipe_day1_dinner');
    expect(plan?.recipes[0].recipe_id).toBe('recipe_day1_dinner');
    expect(plan?.recipes[0].ingredients[0].contribution).toBe('purchase');
    expect(plan?.recipes[0].ingredients[1].contribution).toBe('pantry');
  });

  it('drops unknown contribution roles', () => {
    const plan = normalizeMenuPlan({
      summary: 'Тест',
      total_cost: 0,
      days_plan: [{ day: 'День 1', meals: [{ type: 'lunch', recipe_name: 'Суп' }] }],
      recipes: [
        {
          name: 'Суп',
          ingredients: [{ name: 'Вода', amount: '1 л', contribution: 'unknown_role' }],
          steps: ['Варить'],
        },
      ],
      basket: [{ category: 'Продукты', items: [{ name: 'Вода', weight: '1 л', price: 0 }] }],
    });

    expect(plan?.recipes[0].ingredients[0].contribution).toBeUndefined();
  });

  it('round-trips recipe_id through JSON storage shape', () => {
    const input = {
      summary: 'Тест',
      total_cost: 0,
      days_plan: [
        {
          day: 'День 1',
          meals: [{ type: 'dinner', recipe_name: 'Рыба', recipe_id: 'recipe_day1_dinner' }],
        },
      ],
      recipes: [
        {
          recipe_id: 'recipe_day1_dinner',
          name: 'Рыба',
          ingredients: [{ name: 'Рыба', amount: '300 г' }],
          steps: ['Запечь'],
        },
      ],
      basket: [{ category: 'Продукты', items: [{ name: 'Рыба', weight: '300 г', price: 0 }] }],
    };

    const serialized = JSON.parse(JSON.stringify(input));
    const plan = normalizeMenuPlan(serialized);
    expect(plan?.recipes[0].recipe_id).toBe('recipe_day1_dinner');
  });
});

describe('matchRecipeForMeal', () => {
  const recipes: Recipe[] = [
    {
      name: 'Овсянка',
      recipe_id: 'recipe_a',
      emoji: '🥣',
      cook_time: '10 мин',
      kbju: '',
      ingredients: [],
      steps: [],
    },
    {
      name: 'Овсянка',
      recipe_id: 'recipe_b',
      emoji: '🥣',
      cook_time: '10 мин',
      kbju: '',
      ingredients: [],
      steps: [],
    },
  ];

  it('prefers recipe_id over ambiguous names', () => {
    const match = matchRecipeForMeal(
      { recipe_name: 'Овсянка', recipe_id: 'recipe_b' },
      recipes,
    );
    expect(match.confidence).toBe('id');
    expect(match.recipeIndex).toBe(1);
  });

  it('findRecipeIndexById resolves unique id', () => {
    expect(findRecipeIndexById('recipe_a', recipes)).toBe(0);
    expect(findRecipeIndexById('missing', recipes)).toBeNull();
  });
});
