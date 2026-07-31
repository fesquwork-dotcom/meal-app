import { normalizeDietaryConstraints, toConstraintInputs } from '@/features/profile/dietaryConstraints';
import { PROFILE_BUDGET, PROFILE_DAYS } from '@/features/profile/constants';
import { resolveMealTypes } from '@/types/meal';
import type {
  CookingPreferences,
  PlanningPreferences,
  DietaryConstraint,
  Profile,
  ProfileCooktime,
  ProfileGoal,
  ProfileProtein,
} from '@/types/profile';
import type { MealType } from '@/types/meal';

/** Profile settings stored locally as an unsaved draft (no user_id / updated_at). */
export interface ProfileDraftSettings {
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
  legacy_allergies: string[];
  store: string;
}

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

function safeFiniteNumber(value: unknown, fallback: number): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) {
    return fallback;
  }

  return value;
}

function clampNumber(value: unknown, fallback: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, safeFiniteNumber(value, fallback)));
}

function safeString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback;
}

function normalizeProteins(value: unknown): ProfileProtein[] {
  if (!Array.isArray(value)) {
    return ['any'];
  }

  const normalized = value.filter((item): item is ProfileProtein =>
    typeof item === 'string' && isProtein(item),
  );

  return normalized;
}

function normalizeLegacyAllergies(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0);
}

/** Extracts draft-safe settings from a full profile. */
export function extractProfileDraft(profile: Profile): ProfileDraftSettings {
  return {
    first_name: profile.first_name,
    days: profile.days,
    budget: profile.budget,
    proteins: profile.proteins,
    goal: profile.goal,
    meal_types: profile.meal_types,
    meals_per_day: profile.meals_per_day,
    persons: profile.persons,
    cooktime: profile.cooktime,
    cooking_preferences: profile.cooking_preferences,
    planning_preferences: profile.planning_preferences,
    dietary_constraints: profile.dietary_constraints,
    legacy_allergies: profile.legacy_constraints,
    store: profile.store,
  };
}

/** Payload sent to PUT /api/profile. */
export function profileDraftToSavePayload(draft: ProfileDraftSettings, expectedRevision: number) {
  return {
    ...draft,
    dietary_constraints: toConstraintInputs(draft.dietary_constraints),
    cooking_preferences: {
      prefer_faster_meals: draft.cooking_preferences.prefer_faster_meals,
    },
    planning_preferences: {
      prefer_familiar_meals: draft.planning_preferences.prefer_familiar_meals,
    },
    expected_revision: expectedRevision,
  };
}

/** Applies draft settings on top of a server profile. */
export function applyProfileDraft(serverProfile: Profile, draft: ProfileDraftSettings): Profile {
  const meal_types = resolveMealTypes(draft.meal_types, draft.meals_per_day);

  return {
    ...serverProfile,
    ...draft,
    meal_types,
    meals_per_day: meal_types.length,
    legacy_constraints: draft.legacy_allergies,
    requires_constraint_review: draft.legacy_allergies.length > 0,
    user_id: serverProfile.user_id,
    updated_at: serverProfile.updated_at,
  };
}

/** Normalizes unknown draft payload from storage. */
export function normalizeProfileDraft(raw: unknown): ProfileDraftSettings | null {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) {
    return null;
  }

  const record = raw as Record<string, unknown>;
  const meal_types = resolveMealTypes(
    Array.isArray(record.meal_types)
      ? record.meal_types.filter((item): item is string => typeof item === 'string')
      : null,
    safeFiniteNumber(record.meals_per_day, 3),
  );

  return {
    first_name: safeString(record.first_name),
    days: clampNumber(record.days, 5, PROFILE_DAYS.min, PROFILE_DAYS.max),
    budget: clampNumber(
      record.budget,
      PROFILE_BUDGET.default,
      PROFILE_BUDGET.min,
      PROFILE_BUDGET.max,
    ),
    proteins: normalizeProteins(record.proteins),
    goal: typeof record.goal === 'string' && isGoal(record.goal) ? record.goal : 'home',
    meal_types,
    meals_per_day: meal_types.length,
    persons: safeFiniteNumber(record.persons, 1),
    cooktime:
      typeof record.cooktime === 'string' && isCooktime(record.cooktime)
        ? record.cooktime
        : 'medium',
    cooking_preferences: normalizeCookingPreferences(record.cooking_preferences),
    planning_preferences: normalizePlanningPreferences(record.planning_preferences),
    dietary_constraints: normalizeDietaryConstraints(record.dietary_constraints),
    legacy_allergies: normalizeLegacyAllergies(
      record.legacy_allergies ?? record.legacy_constraints,
    ),
    store: safeString(record.store, 'any'),
  };
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

/** Returns true when cooking preference draft differs from server profile. */
export function isCookingPreferenceDirty(
  serverProfile: Profile,
  draft: ProfileDraftSettings,
): boolean {
  return (
    JSON.stringify(serverProfile.cooking_preferences) !==
    JSON.stringify(draft.cooking_preferences)
  );
}

/** Returns true when draft settings differ from the server profile. */
export function isProfileDraftDirty(
  serverProfile: Profile,
  draft: ProfileDraftSettings,
): boolean {
  return !areProfileSettingsEqual(serverProfile, draft);
}

/** Normalized comparison for conflict auto-resolution. */
export function areProfileSettingsEqual(
  serverProfile: Profile,
  draft: ProfileDraftSettings,
): boolean {
  const serverDraft = extractProfileDraft(serverProfile);
  const serverProteins = [...serverDraft.proteins].sort().join(',');
  const draftProteins = [...draft.proteins].sort().join(',');
  const serverMealTypes = [...serverDraft.meal_types].sort().join(',');
  const draftMealTypes = [...draft.meal_types].sort().join(',');
  const serverConstraints = JSON.stringify(serverDraft.dietary_constraints);
  const draftConstraints = JSON.stringify(draft.dietary_constraints);
  const serverLegacy = [...serverDraft.legacy_allergies].sort().join(',');
  const draftLegacy = [...draft.legacy_allergies].sort().join(',');
  const serverCooking = JSON.stringify(serverDraft.cooking_preferences);
  const draftCooking = JSON.stringify(draft.cooking_preferences);
  const serverPlanning = JSON.stringify(serverDraft.planning_preferences);
  const draftPlanning = JSON.stringify(draft.planning_preferences);

  if (
    serverProteins !== draftProteins ||
    serverMealTypes !== draftMealTypes ||
    serverConstraints !== draftConstraints ||
    serverLegacy !== draftLegacy ||
    serverCooking !== draftCooking ||
    serverPlanning !== draftPlanning
  ) {
    return false;
  }

  return (Object.keys(serverDraft) as (keyof ProfileDraftSettings)[])
    .filter(
      (key) =>
        key !== 'proteins' &&
        key !== 'meal_types' &&
        key !== 'dietary_constraints' &&
        key !== 'legacy_allergies' &&
        key !== 'cooking_preferences' &&
        key !== 'planning_preferences',
    )
    .every((key) => serverDraft[key] === draft[key]);
}
