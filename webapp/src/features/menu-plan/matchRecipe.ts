import type { Recipe } from '@/types/recipe';
import type { DayMeal } from '@/types/menu';

export type RecipeMatchConfidence = 'id' | 'exact' | 'normalized' | 'partial' | 'none';

export interface RecipeMatch {
  recipe: Recipe | null;
  recipeIndex: number | null;
  confidence: RecipeMatchConfidence;
}

const MEAL_PREFIX_PATTERN = /^(завтрак|обед|ужин)\s*:?\s*/i;
const PUNCTUATION_PATTERN = /[.,!?;:()[\]«»""'']/g;
const MIN_PARTIAL_LENGTH = 4;

/** Normalizes a meal or recipe name for comparison. */
export function normalizeMealName(name: string): string {
  let normalized = name.trim().toLowerCase().replace(/ё/g, 'е');
  normalized = normalized.replace(PUNCTUATION_PATTERN, ' ');
  normalized = normalized.replace(/\s+/g, ' ').trim();
  normalized = normalized.replace(MEAL_PREFIX_PATTERN, '').trim();
  return normalized;
}

export function findRecipeIndexById(recipeId: string, recipes: Recipe[]): number | null {
  const trimmed = recipeId.trim();
  if (!trimmed) {
    return null;
  }

  const indices: number[] = [];
  recipes.forEach((recipe, index) => {
    if (recipe.recipe_id?.trim() === trimmed) {
      indices.push(index);
    }
  });

  return indices.length === 1 ? indices[0] : null;
}

export function getRecipeById(recipeId: string, recipes: Recipe[]): Recipe | null {
  const index = findRecipeIndexById(recipeId, recipes);
  return index === null ? null : recipes[index];
}

function findExactMatch(mealName: string, recipes: Recipe[]): number | null {
  const target = mealName.trim().toLowerCase();
  const indices: number[] = [];

  recipes.forEach((recipe, index) => {
    if (recipe.name.trim().toLowerCase() === target) {
      indices.push(index);
    }
  });

  return indices.length === 1 ? indices[0] : null;
}

function findNormalizedMatch(normalizedMeal: string, recipes: Recipe[]): number | null {
  const indices: number[] = [];

  recipes.forEach((recipe, index) => {
    if (normalizeMealName(recipe.name) === normalizedMeal) {
      indices.push(index);
    }
  });

  return indices.length === 1 ? indices[0] : null;
}

function findPartialMatch(normalizedMeal: string, recipes: Recipe[]): number | null {
  if (normalizedMeal.length < MIN_PARTIAL_LENGTH) {
    return null;
  }

  const indices: number[] = [];

  recipes.forEach((recipe, index) => {
    const normalizedRecipe = normalizeMealName(recipe.name);
    if (normalizedRecipe.length < MIN_PARTIAL_LENGTH) {
      return;
    }

    const mealContainsRecipe = normalizedMeal.includes(normalizedRecipe);
    const recipeContainsMeal = normalizedRecipe.includes(normalizedMeal);

    if (mealContainsRecipe || recipeContainsMeal) {
      indices.push(index);
    }
  });

  return indices.length === 1 ? indices[0] : null;
}

function buildMatch(
  recipes: Recipe[],
  index: number | null,
  confidence: RecipeMatchConfidence,
): RecipeMatch {
  if (index === null) {
    return { recipe: null, recipeIndex: null, confidence: 'none' };
  }

  return {
    recipe: recipes[index],
    recipeIndex: index,
    confidence,
  };
}

/**
 * Finds the best matching recipe for a meal, preferring recipe_id when available.
 */
export function matchRecipeForMeal(meal: Pick<DayMeal, 'recipe_name' | 'recipe_id'>, recipes: Recipe[]): RecipeMatch {
  if (meal.recipe_id) {
    const idIndex = findRecipeIndexById(meal.recipe_id, recipes);
    if (idIndex !== null) {
      return buildMatch(recipes, idIndex, 'id');
    }
  }

  return matchRecipe(meal.recipe_name, recipes);
}

/**
 * Finds the best matching recipe for a meal name (legacy fallback).
 * Returns null when ambiguous — never picks a random recipe.
 */
export function matchRecipe(mealName: string, recipes: Recipe[]): RecipeMatch {
  const trimmed = mealName.trim();

  if (!trimmed || recipes.length === 0) {
    return buildMatch(recipes, null, 'none');
  }

  const exactIndex = findExactMatch(trimmed, recipes);
  if (exactIndex !== null) {
    return buildMatch(recipes, exactIndex, 'exact');
  }

  const normalizedMeal = normalizeMealName(trimmed);
  if (!normalizedMeal) {
    return buildMatch(recipes, null, 'none');
  }

  const normalizedIndex = findNormalizedMatch(normalizedMeal, recipes);
  if (normalizedIndex !== null) {
    return buildMatch(recipes, normalizedIndex, 'normalized');
  }

  const partialIndex = findPartialMatch(normalizedMeal, recipes);
  if (partialIndex !== null) {
    return buildMatch(recipes, partialIndex, 'partial');
  }

  return buildMatch(recipes, null, 'none');
}
