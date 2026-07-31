/** Normalized KBJU — Claude returns a string like "Б:25г Ж:10г У:40г". */
export type KbjuValue = string;

export type IngredientContribution = 'purchase' | 'from_source' | 'pantry';

export interface RecipeIngredient {
  name: string;
  amount: string;
  contribution?: IngredientContribution | null;
}

export interface RecipeIngredientApiRecord {
  name?: string;
  amount?: string;
  contribution?: string | null;
}

export interface RecipeSubstitute {
  original: string;
  replacement: string;
}

/**
 * Raw recipe from Claude via POST /api/generate-menu.
 * Extra fields (difficulty, description, etc.) appear in the prompt schema.
 */
export interface RecipeApiRecord {
  name?: string;
  recipe_id?: string | null;
  emoji?: string;
  cook_time?: string | number;
  difficulty?: string;
  calories_per_portion?: string | number;
  description?: string;
  kbju?: string | number | Record<string, unknown> | null;
  ingredients?: RecipeIngredientApiRecord[];
  steps?: string[];
  tips?: string | string[];
  tip?: string;
  substitutes?: Array<Record<string, unknown>>;
}

/** Normalized recipe for frontend use. */
export interface Recipe {
  name: string;
  recipe_id?: string | null;
  emoji: string;
  cook_time: string;
  kbju: KbjuValue;
  ingredients: RecipeIngredient[];
  steps: string[];
  difficulty?: string;
  calories_per_portion?: string;
  description?: string;
  tips?: string[];
  substitutes?: RecipeSubstitute[];
}
