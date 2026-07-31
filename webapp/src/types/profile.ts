import type { MealType } from '@/types/meal';

/** Goal values accepted by POST /api/generate-menu (backend/claude_service.py). */
export type ProfileGoal =
  | 'healthy'
  | 'home'
  | 'muscle'
  | 'weightloss'
  | 'restaurant'
  | 'budget';

/** Protein source values accepted by POST /api/generate-menu. */
export type ProfileProtein =
  | 'chicken'
  | 'beef'
  | 'pork'
  | 'fish'
  | 'seafood'
  | 'eggs'
  | 'veggie'
  | 'any';

/** Cooktime values accepted by POST /api/generate-menu. */
export type ProfileCooktime = 'fast' | 'medium' | 'slow';

export type DietaryConstraintKind = 'allergy' | 'intolerance' | 'preference';

export interface DietaryConstraint {
  id: string;
  kind: DietaryConstraintKind;
  value: string;
}

export interface DietaryConstraintInput {
  id?: string;
  kind: DietaryConstraintKind;
  value: string;
}

/**
 * Raw profile record as returned inside `{ profile: ... }` from GET /api/profile.
 * Nullable fields reflect backend DEFAULT_PROFILE and SQLite storage.
 */
export interface ProfileApiRecord {
  user_id: number;
  first_name: string | null;
  budget: number | null;
  days: number | null;
  meal_types: string[] | null;
  meals_per_day: number | null;
  persons: number | null;
  proteins: string[] | null;
  goal: string | null;
  cooktime: string | null;
  /** @deprecated Legacy raw exclusions; use dietary_constraints + legacy_constraints. */
  allergies?: string | null;
  dietary_constraints?: DietaryConstraint[] | null;
  cooking_preferences?: CookingPreferences | null;
  planning_preferences?: PlanningPreferences | null;
  store: string | null;
  updated_at: string | null;
}

/**
 * Normalized profile used across the app (form state, menu generation).
 * `meals_per_day` is deprecated and derived from `meal_types.length`.
 */
export interface CookingPreferences {
  prefer_faster_meals: boolean | null;
}

export interface PlanningPreferences {
  prefer_familiar_meals: boolean | null;
}

export interface Profile {
  user_id: number;
  first_name: string;
  days: number;
  budget: number;
  proteins: ProfileProtein[];
  goal: ProfileGoal;
  meal_types: MealType[];
  meals_per_day: number;
  persons: number;
  cooktime: ProfileCooktime;
  cooking_preferences: CookingPreferences;
  planning_preferences: PlanningPreferences;
  dietary_constraints: DietaryConstraint[];
  legacy_constraints: string[];
  requires_constraint_review: boolean;
  store: string;
  updated_at: string | null;
}
