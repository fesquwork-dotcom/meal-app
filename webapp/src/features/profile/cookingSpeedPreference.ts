import type { CookingPreferences } from '@/types/profile';

export type CookingSpeedPreferenceValue = 'automatic' | 'faster' | 'ignore';

export const COOKING_SPEED_OPTIONS: ReadonlyArray<{
  value: CookingSpeedPreferenceValue;
  label: string;
}> = [
  { value: 'automatic', label: 'Автоматически' },
  { value: 'faster', label: 'Выбирать более быстрые блюда' },
  { value: 'ignore', label: 'Не учитывать' },
] as const;

const DESCRIPTIONS: Record<CookingSpeedPreferenceValue, string> = {
  automatic:
    'Приложение может учитывать ваши подтверждённые предпочтения из истории замен.',
  faster:
    'При прочих равных приложение будет чаще выбирать блюда, которые требуют меньше времени и действий.',
  ignore: 'История замен не будет влиять на выбор более быстрых блюд.',
};

export function cookingSpeedPreferenceFromProfile(
  preferences: CookingPreferences,
): CookingSpeedPreferenceValue {
  if (preferences.prefer_faster_meals === true) {
    return 'faster';
  }
  if (preferences.prefer_faster_meals === false) {
    return 'ignore';
  }
  return 'automatic';
}

export function cookingPreferencesFromSpeedPreference(
  value: CookingSpeedPreferenceValue,
): CookingPreferences {
  switch (value) {
    case 'faster':
      return { prefer_faster_meals: true };
    case 'ignore':
      return { prefer_faster_meals: false };
    default:
      return { prefer_faster_meals: null };
  }
}

export function cookingSpeedPreferenceDescription(value: CookingSpeedPreferenceValue): string {
  return DESCRIPTIONS[value];
}
