import { describe, expect, it } from 'vitest';
import { COOKING_LABELS } from '@/features/menu-plan/cooking/constants';
import { getCookingStatus } from '@/features/menu-plan/cooking/getCookingStatus';
import type { MealsByIdIndex } from '@/features/menu-plan/cooking/types';
import type { DayMeal } from '@/types/menu';

const mealsById: MealsByIdIndex = {
  day1_dinner: {
    meal_id: 'day1_dinner',
    recipe_name: 'Запечённая курица',
    day_number: 1,
    day_label: 'День 1',
    meal_type: 'dinner',
  },
};

function meal(overrides: Partial<DayMeal>): DayMeal {
  return {
    type: 'lunch',
    recipe_name: 'Блюдо',
    uses_leftovers: false,
    ...overrides,
  };
}

describe('getCookingStatus', () => {
  it('maps requires_cooking=true to cook status', () => {
    const status = getCookingStatus(
      meal({ requires_cooking: true, meal_id: 'day1_lunch', prepared_on_day: 1 }),
      1,
      {},
    );

    expect(status).toEqual({ kind: 'cook', label: COOKING_LABELS.cook });
  });

  it('maps uses_leftovers=true to leftover status with source label', () => {
    const status = getCookingStatus(
      meal({
        requires_cooking: false,
        uses_leftovers: true,
        source_meal_id: 'day1_dinner',
        prepared_on_day: 1,
      }),
      2,
      mealsById,
    );

    expect(status.kind).toBe('leftover');
    expect(status).toMatchObject({
      label: COOKING_LABELS.leftover,
      sourceLabel: 'Основа: Запечённая курица, день 1',
    });
  });

  it('returns leftover without source label when source is missing', () => {
    const status = getCookingStatus(
      meal({ uses_leftovers: true, requires_cooking: false, source_meal_id: 'missing' }),
      2,
      {},
    );

    expect(status).toEqual({ kind: 'leftover', label: COOKING_LABELS.leftover });
  });

  it('maps earlier prepared day to prepared status', () => {
    const status = getCookingStatus(
      meal({ requires_cooking: false, prepared_on_day: 1 }),
      2,
      {},
    );

    expect(status).toEqual({ kind: 'prepared', label: COOKING_LABELS.prepared });
  });

  it('maps no-cook metadata to ready status', () => {
    const status = getCookingStatus(meal({ requires_cooking: false }), 1, {});

    expect(status).toEqual({ kind: 'ready', label: COOKING_LABELS.noCook });
  });

  it('returns unknown for legacy meals', () => {
    const status = getCookingStatus({ type: 'dinner', recipe_name: 'Омлет' }, 1, {});

    expect(status).toEqual({ kind: 'unknown' });
  });

  it('does not mutate input meal', () => {
    const input = meal({ requires_cooking: true, meal_id: 'day1_lunch' });
    const snapshot = { ...input };

    getCookingStatus(input, 1, {});

    expect(input).toEqual(snapshot);
  });
});
