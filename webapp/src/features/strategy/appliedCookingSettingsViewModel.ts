import type { AppliedCookingSettings, CookingPreferenceSource } from '@/types/strategy';

export interface AppliedCookingSettingsViewModel {
  timeLimitLine: string;
  preferenceLine: string;
  sourceLine: string | null;
}

const SOURCE_LABELS: Record<CookingPreferenceSource, string> = {
  profile: 'Задано в профиле',
  learned_preference: 'Учтено по принятому адаптивному предпочтению',
  memory: 'Учтено по подтверждённым заменам',
  default: 'Использовано стандартное правило',
  inferred: 'Источник настройки не сохранён для старого плана',
};

function preferenceEnabledLabel(enabled: boolean): string {
  return enabled ? 'включено' : 'выключено';
}

export function buildAppliedCookingSettingsViewModel(
  settings: AppliedCookingSettings,
): AppliedCookingSettingsViewModel {
  const preferenceLine = `Выбирать более быстрые блюда: ${preferenceEnabledLabel(settings.prefer_faster_meals)}`;
  const timeLimitLine = `Максимальная активная готовка: до ${settings.cooking_time_limit} минут`;
  const sourceLabel = SOURCE_LABELS[settings.preference_source];
  const sourceLine =
    settings.preference_source === 'inferred' ? null : `Источник: ${sourceLabel}`;

  return {
    timeLimitLine,
    preferenceLine,
    sourceLine,
  };
}

export function buildPreviewCookingPreferenceLine(
  settings: AppliedCookingSettings | null | undefined,
): string | null {
  if (!settings) {
    return null;
  }

  if (!settings.prefer_faster_meals && settings.preference_source === 'profile') {
    return 'Предпочтение быстрых блюд отключено в профиле';
  }

  if (settings.prefer_faster_meals && settings.preference_source === 'memory') {
    return 'Более быстрые блюда — по подтверждённым предпочтениям';
  }

  if (settings.prefer_faster_meals && settings.preference_source === 'profile') {
    return 'Более быстрые блюда — задано в профиле';
  }

  if (settings.prefer_faster_meals && settings.preference_source === 'default') {
    return null;
  }

  return null;
}

export function buildNextPlanCookingHint(): string {
  return 'Изменение будет применено к следующему плану.';
}

export { SOURCE_LABELS };
