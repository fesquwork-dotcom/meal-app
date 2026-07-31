import type { Recipe } from '@/types/recipe';

/** Stable machine codes shared with the backend Memory Engine. */
export type ReplacementReasonCode =
  | 'generic'
  | 'faster'
  | 'dislike_ingredient'
  | 'ingredient_unavailable'
  | 'other';

export interface ReplacementReasonPreset {
  id: string;
  label: string;
  reasonCode: ReplacementReasonCode;
  /** Default free-text comment (used only inside the replacement prompt). */
  reason: string;
}

export const REASON_PRESETS: readonly ReplacementReasonPreset[] = [
  { id: 'simple', label: 'Просто заменить', reasonCode: 'generic', reason: '' },
  { id: 'faster', label: 'Хочу быстрее', reasonCode: 'faster', reason: 'Хочу быстрее' },
  { id: 'dislike', label: 'Не нравится продукт', reasonCode: 'dislike_ingredient', reason: 'Не нравится продукт' },
  { id: 'missing', label: 'Нет ингредиента', reasonCode: 'ingredient_unavailable', reason: 'Нет ингредиента в магазине' },
  { id: 'other', label: 'Другая причина', reasonCode: 'other', reason: '' },
] as const;

export function findReasonPreset(presetId: string): ReplacementReasonPreset | undefined {
  return REASON_PRESETS.find((preset) => preset.id === presetId);
}

/** The ingredient selector is only meaningful for ingredient-scoped reasons. */
export function shouldShowIngredientSelector(reasonCode: ReplacementReasonCode | undefined): boolean {
  return reasonCode === 'dislike_ingredient' || reasonCode === 'ingredient_unavailable';
}

/**
 * Builds the optional ingredient options from the target recipe.
 * Pantry ingredients (соль, вода, …) are hidden; canonical names are never exposed.
 */
export function buildIngredientOptions(recipe: Recipe | null | undefined): string[] {
  if (!recipe?.ingredients?.length) {
    return [];
  }

  const seen = new Set<string>();
  const options: string[] = [];
  for (const ingredient of recipe.ingredients) {
    if (ingredient.contribution === 'pantry') {
      continue;
    }
    const name = ingredient.name?.trim();
    if (!name) {
      continue;
    }
    const key = name.toLowerCase();
    if (seen.has(key)) {
      continue;
    }
    seen.add(key);
    options.push(name);
  }
  return options;
}
