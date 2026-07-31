import { describe, expect, it } from 'vitest';
import { matchRecipe } from '@/features/menu-plan/matchRecipe';
import type { Recipe } from '@/types/recipe';

const recipes: Recipe[] = [
  {
    name: 'Овсянка с ягодами',
    emoji: '🥣',
    cook_time: '15 мин',
    kbju: '',
    ingredients: [],
    steps: [],
  },
  {
    name: 'Куриный суп',
    emoji: '🍲',
    cook_time: '40 мин',
    kbju: '',
    ingredients: [],
    steps: [],
  },
  {
    name: 'Гречка с котлетой',
    emoji: '🍽',
    cook_time: '30 мин',
    kbju: '',
    ingredients: [],
    steps: [],
  },
];

describe('matchRecipe', () => {
  it('matches exact names', () => {
    const result = matchRecipe('Куриный суп', recipes);
    expect(result.confidence).toBe('exact');
    expect(result.recipeIndex).toBe(1);
    expect(result.recipe?.name).toBe('Куриный суп');
  });

  it('matches normalized names with punctuation', () => {
    const result = matchRecipe('  овсянка с ягодами!!! ', recipes);
    expect(result.confidence).toBe('normalized');
    expect(result.recipeIndex).toBe(0);
  });

  it('treats ё and е as equivalent', () => {
    const yoRecipes: Recipe[] = [
      {
        name: 'Жарёная картошка',
        emoji: '🥔',
        cook_time: '20 мин',
        kbju: '',
        ingredients: [],
        steps: [],
      },
    ];

    const result = matchRecipe('Жареная картошка', yoRecipes);
    expect(result.confidence).toBe('normalized');
    expect(result.recipeIndex).toBe(0);
  });

  it('strips meal prefixes like «Ужин:»', () => {
    const result = matchRecipe('Ужин: Гречка с котлетой', recipes);
    expect(result.confidence).toBe('normalized');
    expect(result.recipeIndex).toBe(2);
  });

  it('matches unique partial inclusion', () => {
    const result = matchRecipe('Куриный суп с лапшой', recipes);
    expect(result.confidence).toBe('partial');
    expect(result.recipeIndex).toBe(1);
  });

  it('returns none for ambiguous partial matches', () => {
    const ambiguousRecipes: Recipe[] = [
      { ...recipes[0], name: 'Овощной суп' },
      { ...recipes[1], name: 'Суп пюре' },
    ];

    const result = matchRecipe('Овощной суп пюре', ambiguousRecipes);
    expect(result.confidence).toBe('none');
    expect(result.recipe).toBeNull();
    expect(result.recipeIndex).toBeNull();
  });

  it('returns none for empty meal name', () => {
    const result = matchRecipe('   ', recipes);
    expect(result.confidence).toBe('none');
    expect(result.recipe).toBeNull();
  });
});
