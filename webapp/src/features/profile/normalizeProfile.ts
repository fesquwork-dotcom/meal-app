import {
  DEFAULT_MEAL_TYPES,
  mealTypesFromCount,
  resolveMealTypes,
} from '@/types/meal';
import { resolveProfileConstraints } from '@/features/profile/dietaryConstraints';
import { PROFILE_BUDGET, PROFILE_DAYS } from '@/features/profile/constants';
import type {
  CookingPreferences,
  Profile,
  ProfileApiRecord,
  ProfileCooktime,
  ProfileGoal,
  PlanningPreferences,
  ProfileProtein,
} from '@/types/profile';

const GOAL_VALUES: ProfileGoal[] = [
  'healthy',
  'home',
  'muscle',
  'weightloss',
  'restaurant',
  'budget',
];

const PROTEIN_VALUES: ProfileProtein[] = [
  'chicken',
  'beef',
  'pork',
  'fish',
  'seafood',
  'eggs',
  'veggie',
  'any',
];

const COOKTIME_VALUES: ProfileCooktime[] = ['fast', 'medium', 'slow'];

function isGoal(value: string): value is ProfileGoal {
  return (GOAL_VALUES as string[]).includes(value);
}

function isProtein(value: string): value is ProfileProtein {
  return (PROTEIN_VALUES as string[]).includes(value);
}

function isCooktime(value: string): value is ProfileCooktime {
  return (COOKTIME_VALUES as string[]).includes(value);
}

function normalizeCookingPreferences(raw: unknown): CookingPreferences {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return { prefer_faster_meals: null };
  }
  const value = (raw as Record<string, unknown>).prefer_faster_meals;
  if (value === true || value === false) {
    return { prefer_faster_meals: value };
  }
  return { prefer_faster_meals: null };
}

function normalizePlanningPreferences(raw: unknown): PlanningPreferences {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return { prefer_familiar_meals: null };
  }
  const value = (raw as Record<string, unknown>).prefer_familiar_meals;
  if (value === true || value === false) {
    return { prefer_familiar_meals: value };
  }
  return { prefer_familiar_meals: null };
}

function normalizeProteins(proteins: string[] | null | undefined): ProfileProtein[] {
  if (proteins === null || proteins === undefined) {
    return ['any'];
  }

  if (proteins.length === 0) {
    return [];
  }

  const normalized = proteins.filter(isProtein);
  return normalized.length > 0 ? normalized : [];
}

function clampProfileNumber(
  value: number | null | undefined,
  fallback: number,
  min: number,
  max: number,
): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return fallback;
  }
  return Math.min(max, Math.max(min, value));
}

export interface NormalizeProfileOptions {
  legacy_constraints?: string[];
  requires_constraint_review?: boolean;
}

/** Maps a raw backend profile to a fully populated client Profile. */
export function normalizeProfile(
  raw: ProfileApiRecord,
  options: NormalizeProfileOptions = {},
): Profile {
  const meal_types = resolveMealTypes(raw.meal_types, raw.meals_per_day);
  const constraintFields = resolveProfileConstraints(raw, options.legacy_constraints);

  return {
    user_id: raw.user_id,
    first_name: raw.first_name ?? '',
    days: clampProfileNumber(raw.days, 5, PROFILE_DAYS.min, PROFILE_DAYS.max),
    budget: clampProfileNumber(
      raw.budget,
      PROFILE_BUDGET.default,
      PROFILE_BUDGET.min,
      PROFILE_BUDGET.max,
    ),
    proteins: normalizeProteins(raw.proteins),
    goal: raw.goal && isGoal(raw.goal) ? raw.goal : 'home',
    meal_types,
    meals_per_day: meal_types.length,
    persons: raw.persons ?? 1,
    cooktime: raw.cooktime && isCooktime(raw.cooktime) ? raw.cooktime : 'medium',
    cooking_preferences: normalizeCookingPreferences(raw.cooking_preferences),
    planning_preferences: normalizePlanningPreferences(raw.planning_preferences),
    dietary_constraints: constraintFields.dietary_constraints,
    legacy_constraints: constraintFields.legacy_constraints,
    requires_constraint_review:
      options.requires_constraint_review ?? constraintFields.requires_constraint_review,
    store: raw.store ?? 'any',
    updated_at: raw.updated_at ?? null,
  };
}

/** Default profile for empty/error fallback UI (matches backend DEFAULT_PROFILE + MenuRequest defaults). */
export function createDefaultProfile(userId: number): Profile {
  return normalizeProfile({
    user_id: userId,
    first_name: '',
    budget: null,
    days: 5,
    meal_types: null,
    meals_per_day: null,
    persons: 1,
    proteins: ['any'],
    goal: 'home',
    cooktime: 'medium',
    cooking_preferences: { prefer_faster_meals: null },
    planning_preferences: { prefer_familiar_meals: null },
    dietary_constraints: [],
    store: 'any',
    updated_at: null,
  });
}

export { mealTypesFromCount, resolveMealTypes, DEFAULT_MEAL_TYPES };
