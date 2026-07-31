import type { PlanningPreferences } from '@/types/profile';

export type FamiliarMealsPreferenceValue = 'unset' | 'enabled' | 'disabled';

export const FAMILIAR_MEALS_OPTIONS: ReadonlyArray<{
  value: FamiliarMealsPreferenceValue;
  label: string;
}> = [
  { value: 'unset', label: 'Не задано' },
  { value: 'enabled', label: 'Включено' },
  { value: 'disabled', label: 'Отключено' },
] as const;

const DESCRIPTIONS: Record<FamiliarMealsPreferenceValue, string> = {
  unset:
    'Приложение не будет специально отдавать предпочтение более знакомым блюдам, пока вы не включите настройку.',
  enabled:
    'При прочих равных следующие планы будут предпочитать более знакомые и предсказуемые блюда.',
  disabled:
    'Предпочтение знакомых блюд явно не применяется, даже если приложение заметило частые замены.',
};

export function familiarMealsPreferenceFromProfile(
  preferences: PlanningPreferences,
): FamiliarMealsPreferenceValue {
  if (preferences.prefer_familiar_meals === true) {
    return 'enabled';
  }
  if (preferences.prefer_familiar_meals === false) {
    return 'disabled';
  }
  return 'unset';
}

export function planningPreferencesFromFamiliarMealsValue(
  value: FamiliarMealsPreferenceValue,
): PlanningPreferences {
  switch (value) {
    case 'enabled':
      return { prefer_familiar_meals: true };
    case 'disabled':
      return { prefer_familiar_meals: false };
    default:
      return { prefer_familiar_meals: null };
  }
}

export function familiarMealsPreferenceDescription(value: FamiliarMealsPreferenceValue): string {
  return DESCRIPTIONS[value];
}
