import type { StrategyInputChangeMessageKey } from '@/features/strategy-inputs/types';

const MESSAGES: Record<StrategyInputChangeMessageKey, string> = {
  profile_changed: 'Настройки профиля изменились. Проверьте будущий план ещё раз.',
  memory_changed: 'Сохранённые предпочтения изменились. Проверьте будущий план ещё раз.',
  behavior_changed: 'Подтверждённые наблюдения изменились. Проверьте будущий план ещё раз.',
  learned_preference_changed:
    'Адаптивные предпочтения изменились. Проверьте будущий план ещё раз.',
  conflict_resolved: 'Конфликт разрешён. Постройте новое предварительное описание плана.',
  plan_date_changed: 'Дата начала изменилась. Проверьте план ещё раз.',
  settings_changed: 'Настройки будущего плана изменились. Проверьте его ещё раз.',
  server_profile_changed: 'Профиль изменился в другой сессии. Проверьте будущий план ещё раз.',
  server_memory_changed:
    'Сохранённые предпочтения изменились. Постройте новое предварительное описание плана.',
  server_behavior_changed:
    'Подтверждённые наблюдения изменились. Проверьте будущий план ещё раз.',
  server_learned_preferences_changed:
    'Адаптивные предпочтения изменились. Проверьте будущий план ещё раз.',
  preview_expired: 'Время предварительного просмотра истекло. Проверьте план ещё раз.',
  application_updated: 'Приложение обновилось. Постройте предварительное описание плана заново.',
  preview_invalid: 'Предварительное описание больше нельзя использовать. Создайте его заново.',
};

/** Higher wins when replacing stale copy without a full reset. */
const MESSAGE_PRIORITY: Record<StrategyInputChangeMessageKey, number> = {
  application_updated: 60,
  server_profile_changed: 50,
  server_memory_changed: 50,
  server_behavior_changed: 50,
  server_learned_preferences_changed: 50,
  preview_expired: 40,
  preview_invalid: 30,
  conflict_resolved: 20,
  profile_changed: 10,
  memory_changed: 10,
  behavior_changed: 10,
  learned_preference_changed: 10,
  plan_date_changed: 10,
  settings_changed: 5,
};

export function getStrategyInputChangeMessage(
  key: StrategyInputChangeMessageKey | null | undefined,
): string | null {
  if (!key) {
    return null;
  }
  return MESSAGES[key] ?? MESSAGES.settings_changed;
}

export function getStrategyInputMessagePriority(
  key: StrategyInputChangeMessageKey | null | undefined,
): number {
  if (!key) {
    return 0;
  }
  return MESSAGE_PRIORITY[key] ?? 0;
}

export function shouldReplaceStaleMessage(
  currentKey: StrategyInputChangeMessageKey | null | undefined,
  nextKey: StrategyInputChangeMessageKey | null | undefined,
): boolean {
  if (!nextKey) {
    return false;
  }
  if (!currentKey) {
    return true;
  }
  return getStrategyInputMessagePriority(nextKey) > getStrategyInputMessagePriority(currentKey);
}
