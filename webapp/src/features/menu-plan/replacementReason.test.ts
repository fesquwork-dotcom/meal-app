import { describe, expect, it } from 'vitest';

import {
  REASON_PRESETS,
  buildIngredientOptions,
  findReasonPreset,
  shouldShowIngredientSelector,
} from '@/features/menu-plan/replacementReason';
import type { Recipe } from '@/types/recipe';

describe('replacement reason mapping', () => {
  it('maps each preset to a stable machine reason code', () => {
    const codes = REASON_PRESETS.map((preset) => preset.reasonCode);
    expect(codes).toEqual([
      'generic',
      'faster',
      'dislike_ingredient',
      'ingredient_unavailable',
      'other',
    ]);
  });

  it('finds a preset by id', () => {
    expect(findReasonPreset('dislike')?.reasonCode).toBe('dislike_ingredient');
    expect(findReasonPreset('missing')?.reasonCode).toBe('ingredient_unavailable');
    expect(findReasonPreset('unknown')).toBeUndefined();
  });
});

describe('ingredient selector visibility', () => {
  it('shows selector only for ingredient-scoped reasons', () => {
    expect(shouldShowIngredientSelector('dislike_ingredient')).toBe(true);
    expect(shouldShowIngredientSelector('ingredient_unavailable')).toBe(true);
    expect(shouldShowIngredientSelector('faster')).toBe(false);
    expect(shouldShowIngredientSelector('generic')).toBe(false);
    expect(shouldShowIngredientSelector('other')).toBe(false);
    expect(shouldShowIngredientSelector(undefined)).toBe(false);
  });
});

describe('ingredient options', () => {
  const recipe: Recipe = {
    name: 'Гречка с курицей',
    emoji: '🍲',
    cook_time: '30 мин',
    kbju: '',
    ingredients: [
      { name: 'Гречка', amount: '200 г', contribution: 'purchase' },
      { name: 'Куриная грудка', amount: '300 г', contribution: 'purchase' },
      { name: 'Соль', amount: 'по вкусу', contribution: 'pantry' },
      { name: 'Гречка', amount: 'дубль', contribution: 'purchase' },
    ],
    steps: ['Готовить'],
  };

  it('lists non-pantry ingredients without duplicates', () => {
    expect(buildIngredientOptions(recipe)).toEqual(['Гречка', 'Куриная грудка']);
  });

  it('returns empty list for missing recipe', () => {
    expect(buildIngredientOptions(null)).toEqual([]);
    expect(buildIngredientOptions(undefined)).toEqual([]);
  });
});
