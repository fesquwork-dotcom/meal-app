import type { StrategyWorkflowErrorKind } from '@/features/strategy-workflow/types';

const KIND_FALLBACKS: Record<StrategyWorkflowErrorKind, string> = {
  stale: 'Настройки будущего плана изменились. Проверьте его ещё раз.',
  validation: 'Проверьте введённые данные.',
  conflict: 'Нужно устранить противоречие в настройках.',
  retryable: 'Временная ошибка. Попробуйте ещё раз.',
  authentication: 'Не удалось подтвердить вход через Telegram. Перезапустите приложение.',
  not_found: 'Запрошенные данные больше недоступны.',
  rate_limited: 'Слишком много запросов. Попробуйте ещё раз немного позже.',
  service_unavailable: 'Сервис временно недоступен. Попробуйте позже.',
  fatal: 'Не удалось выполнить действие. Попробуйте позже.',
  unknown: 'Произошла неизвестная ошибка.',
};

/** One backend code → one primary user-facing text. */
const CODE_MESSAGES: Record<string, string> = {
  STRATEGY_PREVIEW_VERSION_MISMATCH:
    'Приложение обновилось. Постройте предварительное описание плана заново.',
  STRATEGY_PREVIEW_STALE_PROFILE:
    'Профиль изменился в другой сессии. Проверьте будущий план ещё раз.',
  STRATEGY_PREVIEW_STALE_MEMORY:
    'Сохранённые предпочтения изменились. Постройте новое предварительное описание плана.',
  STRATEGY_PREVIEW_STALE_BEHAVIOR:
    'Подтверждённые наблюдения изменились. Проверьте будущий план ещё раз.',
  STRATEGY_PREVIEW_STALE_LEARNED_PREFERENCES:
    'Адаптивные предпочтения изменились. Проверьте будущий план ещё раз.',
  STRATEGY_PREVIEW_STALE: 'Настройки изменились. Проверьте план ещё раз.',
  STRATEGY_PREVIEW_EXPIRED: 'Время предварительного просмотра истекло. Проверьте план ещё раз.',
  STRATEGY_PREVIEW_INVALID:
    'Предварительное описание больше нельзя использовать. Создайте его заново.',
  STRATEGY_PREVIEW_TOKEN_MISSING:
    'Предварительное описание больше нельзя использовать. Создайте его заново.',
  STRATEGY_PREVIEW_REQUIRED:
    'Сначала постройте предварительное описание плана.',

  CONFLICT_NOT_FOUND: 'Это противоречие уже не актуально.',
  CONFLICT_ACTION_NOT_ALLOWED: 'Не удалось применить выбранное действие.',
  CONSTRAINT_NOT_REMOVABLE: 'Это ограничение можно изменить только в настройках профиля.',

  PROFILE_REQUIRED: 'Заполните профиль, чтобы продолжить.',
  PROFILE_INVALID: 'Проверьте настройки профиля.',
  PROFILE_INCOMPLETE: 'Заполните обязательные настройки профиля.',
  PROFILE_STALE: 'Профиль изменился в другой сессии. Загрузите сохранённые настройки.',
  PROFILE_PROTEIN_REQUIRED: 'Выберите источник белка.',
  PROFILE_PROTEIN_EXCLUDED: 'Выбранный белок исключён настройками.',
  PROFILE_ANY_WITH_SPECIFIC_PROTEINS: 'Нельзя совмещать «любой белок» с конкретными источниками.',
  PROFILE_TOO_MANY_CONSTRAINTS: 'Слишком много ограничений. Упростите настройки.',
  PROFILE_CONSTRAINT_VALUE_EMPTY: 'Укажите значение ограничения.',
  PROFILE_CONSTRAINT_ID_INVALID: 'Некорректное ограничение в профиле.',
  PROFILE_REQUIRES_PROTEIN_SELECTION: 'Выберите новый источник белка.',
  PERSISTED_PROFILE_INVALID: 'Сохранённый профиль нужно обновить.',
  NO_ALLOWED_PREFERRED_PROTEINS: 'Нет доступных источников белка для плана.',
  REQUEST_VALIDATION_ERROR: 'Проверьте введённые данные.',

  MEMORY_PROMOTION_PROFILE_STALE:
    'Профиль изменился в другой сессии. Обновите данные и попробуйте снова.',
  MEMORY_PROMOTION_FAILED: 'Не удалось добавить в профиль. Попробуйте ещё раз.',
  MEMORY_SIGNAL_NOT_FOUND: 'Это наблюдение больше не актуально.',

  BEHAVIOR_INSIGHT_NOT_FOUND: 'Это наблюдение больше не актуально.',
  BEHAVIOR_INSIGHT_NOT_CONFIRMABLE: 'Наблюдение уже изменилось. Обновите список.',
  BEHAVIOR_INSIGHT_NOT_DISMISSIBLE: 'Наблюдение уже изменилось. Обновите список.',
  BEHAVIOR_INSIGHT_NOT_SNOOZABLE: 'Это наблюдение нельзя отложить.',
  BEHAVIOR_INSIGHT_NOT_REVOKABLE: 'Это наблюдение нельзя отозвать.',
  BEHAVIOR_SNOOZE_FAILED: 'Не удалось отложить наблюдение. Попробуйте ещё раз.',
  BEHAVIOR_REVOKE_FAILED: 'Не удалось отозвать наблюдение. Попробуйте ещё раз.',
  BEHAVIOR_SERVICE_UNAVAILABLE: 'Не удалось загрузить наблюдения приложения.',
  BEHAVIOR_RECOMMENDATION_NOT_AVAILABLE: 'Это предложение сейчас недоступно.',
  BEHAVIOR_RECOMMENDATION_ALREADY_APPLIED: 'Предложение уже было применено ранее.',
  BEHAVIOR_RECOMMENDATION_PROFILE_STALE:
    'Профиль изменился в другой сессии. Обновите данные и попробуйте снова.',
  BEHAVIOR_RECOMMENDATION_FAILED: 'Не удалось сохранить настройку. Попробуйте ещё раз.',

  STRATEGY_COMPARE_FAILED: 'Не удалось сравнить планы. Попробуйте ещё раз.',
  STRATEGY_COMPARE_NOT_AVAILABLE: 'Сравнение планов сейчас недоступно.',
  STRATEGY_COMPARE_UNSUPPORTED_VERSION: 'Эта версия плана не поддерживает сравнение.',
  STRATEGY_SAVE_FAILED: 'Не удалось сохранить план. Попробуйте ещё раз.',
  STRATEGY_NOT_FOUND: 'План не найден.',
  STRATEGY_NOT_ACTIVE: 'Этот план уже не активен.',

  REPLACEMENT_NOT_FOUND: 'Блюдо для замены не найдено.',
  REPLACEMENT_INVALID: 'Не удалось выполнить замену с этими параметрами.',
  REPLACEMENT_FAILED: 'Не удалось заменить блюдо. Попробуйте ещё раз.',
  REPLACEMENT_PRICE_UNRESOLVED:
    'Не удалось рассчитать стоимость продуктов для нового блюда. Текущий план не изменён. Попробуйте ещё раз.',

  MENU_GENERATION_INVALID: 'Не удалось сформировать корректное меню. Попробуйте ещё раз.',
  MENU_GENERATION_OUTPUT_TRUNCATED: 'Не удалось сформировать полное меню. Попробуйте ещё раз.',
  MENU_GENERATION_TIMEOUT: 'Генерация заняла слишком много времени. Попробуйте ещё раз.',
  MENU_GENERATION_UNAVAILABLE: 'Сервис генерации временно недоступен.',
  INTERNAL_ERROR: 'Не удалось выполнить действие. Текущие данные не изменены.',

  CLIENT_NETWORK_ERROR: 'Нет соединения с сервером. Проверьте интернет и повторите попытку.',
  CLIENT_TIMEOUT: 'Превышено время ожидания. Попробуйте ещё раз.',
  CLIENT_RATE_LIMITED: 'Слишком много запросов. Попробуйте ещё раз немного позже.',
  CLIENT_UNKNOWN_ERROR: 'Произошла неизвестная ошибка.',
};

const TECHNICAL_MESSAGE_MARKERS = [
  'traceback',
  'sqlalchemy',
  'psycopg',
  'stack',
  'exception',
  'token',
  'prompt',
];

export function getStrategyWorkflowCodeMessage(code: string): string | null {
  return CODE_MESSAGES[code] ?? null;
}

export function getStrategyWorkflowKindFallback(kind: StrategyWorkflowErrorKind): string {
  return KIND_FALLBACKS[kind];
}

export function isTechnicalBackendMessage(message: string): boolean {
  const lower = message.toLowerCase();
  return TECHNICAL_MESSAGE_MARKERS.some((marker) => lower.includes(marker));
}

export function resolveStrategyWorkflowMessage(args: {
  code: string;
  kind: StrategyWorkflowErrorKind;
  backendMessage: string | null;
}): string {
  const known = getStrategyWorkflowCodeMessage(args.code);
  if (known) {
    return known;
  }
  if (args.backendMessage && !isTechnicalBackendMessage(args.backendMessage)) {
    return args.backendMessage;
  }
  return getStrategyWorkflowKindFallback(args.kind);
}
