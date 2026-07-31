import type { AppliedPlanningSettings, FamiliarMealsSource } from '@/types/strategy';

export interface AppliedPlanningSettingsViewModel {
  preferenceLine: string;
  sourceLine: string | null;
}

const SOURCE_LABELS: Record<FamiliarMealsSource, string> = {
  profile: 'Задано в профиле',
  learned_preference: 'Учтено по принятому адаптивному предпочтению',
  default: 'Использовано стандартное правило',
  inferred: 'Источник настройки не сохранён для старого плана',
};

export function buildAppliedPlanningSettingsViewModel(
  settings: AppliedPlanningSettings,
): AppliedPlanningSettingsViewModel {
  const enabledLabel = settings.prefer_familiar_meals ? 'включено' : 'выключено';
  const preferenceLine = `Предпочтение знакомых блюд: ${enabledLabel}`;
  const sourceLabel = SOURCE_LABELS[settings.familiar_meals_source];
  const sourceLine =
    settings.familiar_meals_source === 'inferred' ? null : `Источник: ${sourceLabel}`;

  return {
    preferenceLine,
    sourceLine,
  };
}

export function buildPreviewPlanningPreferenceLine(
  settings: AppliedPlanningSettings | null | undefined,
): string | null {
  if (!settings?.prefer_familiar_meals) {
    return null;
  }

  if (settings.familiar_meals_source === 'profile') {
    return 'Более знакомые блюда — включено в профиле';
  }

  return null;
}
