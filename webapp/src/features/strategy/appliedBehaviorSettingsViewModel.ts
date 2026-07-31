import type { AppliedBehaviorSettings } from '@/types/strategy';

export function buildAppliedBehaviorSettingsLine(
  settings: AppliedBehaviorSettings | null | undefined,
): string | null {
  if (!settings || settings.applied_count <= 0) {
    return null;
  }

  if (settings.availability_preferences_applied) {
    return 'Учтено подтверждённое наблюдение о доступности продуктов';
  }

  return `Наблюдения приложения: учтено ${settings.applied_count}`;
}

export function buildPreviewBehaviorLine(
  settings: AppliedBehaviorSettings | null | undefined,
): string | null {
  if (!settings || settings.applied_count <= 0) {
    return null;
  }

  if (settings.availability_preferences_applied) {
    return 'Учтено подтверждённое наблюдение о доступности продуктов';
  }

  return null;
}
