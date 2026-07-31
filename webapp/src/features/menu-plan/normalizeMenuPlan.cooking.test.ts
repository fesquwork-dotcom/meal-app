import { describe, expect, it } from 'vitest';
import { normalizeMenuPlan } from '@/features/menu-plan/normalizeMenuPlan';
import { wrapForStorage, unwrapFromStorage } from '@/lib/storageVersion';

const basePlan = {
  summary: 'План',
  plan_start_date: '2026-07-13',
  total_cost: 1000,
  recipes: [
    {
      name: 'Курица',
      emoji: '🍗',
      ingredients: [{ name: 'курица', amount: '1' }],
      steps: ['Готовить'],
    },
  ],
  basket: [{ category: 'Мясо', items: [{ name: 'курица', weight: '1 кг', price: 1000 }] }],
};

describe('normalizeMenuPlan cooking metadata', () => {
  it('preserves valid plan_start_date', () => {
    const plan = normalizeMenuPlan({
      ...basePlan,
      days_plan: [{ day: 'День 1', meals: [{ type: 'dinner', recipe_name: 'Курица' }] }],
    });

    expect(plan?.plan_start_date).toBe('2026-07-13');
  });

  it('drops invalid plan_start_date without breaking menu', () => {
    const plan = normalizeMenuPlan({
      ...basePlan,
      plan_start_date: '2026-02-31',
      days_plan: [{ day: 'День 1', meals: [{ type: 'dinner', recipe_name: 'Курица' }] }],
    });

    expect(plan?.plan_start_date).toBeUndefined();
    expect(plan?.days_plan[0].meals[0].recipe_name).toBe('Курица');
  });

  it('preserves cooking metadata fields', () => {
    const plan = normalizeMenuPlan({
      ...basePlan,
      days_plan: [
        {
          day: 'День 1',
          meals: [
            {
              type: 'dinner',
              recipe_name: 'Запечённая курица',
              meal_id: 'day1_dinner',
              requires_cooking: true,
              prepared_on_day: 1,
              uses_leftovers: false,
              source_meal_id: null,
            },
          ],
        },
      ],
    });

    expect(plan?.days_plan[0].meals[0]).toMatchObject({
      type: 'dinner',
      recipe_name: 'Запечённая курица',
      meal_id: 'day1_dinner',
      requires_cooking: true,
      prepared_on_day: 1,
      uses_leftovers: false,
      source_meal_id: null,
    });
  });

  it('keeps false as false for requires_cooking', () => {
    const plan = normalizeMenuPlan({
      ...basePlan,
      days_plan: [
        {
          day: 'День 2',
          meals: [
            {
              type: 'lunch',
              recipe_name: 'Боул',
              requires_cooking: false,
              uses_leftovers: true,
              source_meal_id: 'day1_dinner',
            },
          ],
        },
      ],
    });

    expect(plan?.days_plan[0].meals[0].requires_cooking).toBe(false);
    expect(plan?.days_plan[0].meals[0].uses_leftovers).toBe(true);
  });

  it('handles null optional fields', () => {
    const plan = normalizeMenuPlan({
      ...basePlan,
      days_plan: [
        {
          day: 'День 1',
          meals: [
            {
              type: 'breakfast',
              recipe_name: 'Овсянка',
              meal_id: null,
              requires_cooking: null,
              prepared_on_day: null,
              source_meal_id: null,
            },
          ],
        },
      ],
    });

    expect(plan?.days_plan[0].meals[0]).toMatchObject({
      type: 'breakfast',
      recipe_name: 'Овсянка',
      meal_id: null,
      requires_cooking: null,
      prepared_on_day: null,
      uses_leftovers: false,
      source_meal_id: null,
    });
  });

  it('drops invalid prepared_on_day without breaking menu', () => {
    const plan = normalizeMenuPlan({
      ...basePlan,
      days_plan: [
        {
          day: 'День 1',
          meals: [
            {
              type: 'dinner',
              recipe_name: 'Рыба',
              prepared_on_day: -1,
              requires_cooking: true,
            },
          ],
        },
      ],
    });

    expect(plan?.days_plan[0].meals[0].prepared_on_day).toBeUndefined();
    expect(plan?.days_plan[0].meals[0].recipe_name).toBe('Рыба');
  });

  it('normalizes legacy meal without cooking fields', () => {
    const plan = normalizeMenuPlan({
      ...basePlan,
      days_plan: [
        {
          day: 'День 1',
          breakfast: 'Овсянка',
          lunch: 'Борщ',
          dinner: 'Рыба',
        },
      ],
    });

    expect(plan?.days_plan[0].meals[0]).toEqual({
      type: 'breakfast',
      recipe_name: 'Овсянка',
      uses_leftovers: false,
    });
  });

  it('preserves meal_id string without mutation', () => {
    const plan = normalizeMenuPlan({
      ...basePlan,
      days_plan: [
        {
          day: 'День 1',
          meals: [{ type: 'dinner', recipe_name: 'Курица', meal_id: 'day1_dinner' }],
        },
      ],
    });

    expect(plan?.days_plan[0].meals[0].meal_id).toBe('day1_dinner');
  });

  it('round-trips cooking metadata through storage envelope', () => {
    const raw = {
      ...basePlan,
      days_plan: [
        {
          day: 'День 2',
          meals: [
            {
              type: 'lunch',
              recipe_name: 'Боул с курицей',
              meal_id: 'day2_lunch',
              requires_cooking: false,
              prepared_on_day: 1,
              uses_leftovers: true,
              source_meal_id: 'day1_dinner',
            },
          ],
        },
      ],
    };

    const normalized = normalizeMenuPlan(raw);
    const stored = wrapForStorage(normalized);
    const loaded = unwrapFromStorage<unknown>(stored);
    const roundTripped = normalizeMenuPlan(loaded);

    expect(roundTripped?.days_plan[0].meals[0]).toMatchObject({
      meal_id: 'day2_lunch',
      requires_cooking: false,
      prepared_on_day: 1,
      uses_leftovers: true,
      source_meal_id: 'day1_dinner',
    });
    expect(roundTripped?.plan_start_date).toBe('2026-07-13');
  });

  it('loads legacy storage without assigning today as start date', () => {
    const normalized = normalizeMenuPlan({
      ...basePlan,
      plan_start_date: undefined,
      days_plan: [{ day: 'День 1', meals: [{ type: 'dinner', recipe_name: 'Омлет' }] }],
    });
    const stored = wrapForStorage(normalized);
    const roundTripped = normalizeMenuPlan(unwrapFromStorage<unknown>(stored));

    expect(roundTripped?.plan_start_date).toBeUndefined();
    expect(roundTripped?.days_plan[0].meals[0].recipe_name).toBe('Омлет');
  });
});
