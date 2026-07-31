import type { StrategyWorkflowFieldError } from '@/features/strategy-workflow/types';

const PROFILE_FIELD_MAP: Record<string, string> = {
  'profile.budget': 'budget',
  'profile.proteins': 'proteins',
  'profile.cooktime': 'cooktime',
  'profile.dietary_constraints': 'dietary_constraints',
  'profile.days': 'days',
  'profile.persons': 'persons',
  'profile.goal': 'goal',
  'profile.store': 'store',
  'profile.meal_types': 'meal_types',
};

/** Maps backend field path to Profile form field key when known. */
export function mapWorkflowFieldToProfileKey(field: string): string | null {
  if (PROFILE_FIELD_MAP[field]) {
    return PROFILE_FIELD_MAP[field];
  }
  if (field.startsWith('profile.')) {
    return field.slice('profile.'.length) || null;
  }
  return null;
}

export function buildProfileFieldErrorMap(
  fieldErrors: StrategyWorkflowFieldError[],
): Record<string, string> {
  const mapped: Record<string, string> = {};
  for (const item of fieldErrors) {
    const key = mapWorkflowFieldToProfileKey(item.field) ?? item.field;
    mapped[key] = item.message;
  }
  return mapped;
}
