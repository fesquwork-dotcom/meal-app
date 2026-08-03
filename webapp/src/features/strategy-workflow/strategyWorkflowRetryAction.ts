import type {
  StrategyWorkflowError,
  WorkflowRetryAction,
} from '@/features/strategy-workflow/types';

const RETRY_LABELS: Record<WorkflowRetryAction, string | null> = {
  retry_same_request: 'Повторить',
  build_new_preview: 'Проверить план ещё раз',
  open_profile: 'Открыть профиль',
  reload_profile: 'Загрузить сохранённые настройки',
  restart_app: 'Перезапустить приложение',
  none: null,
};

const GENERATION_RETRY_CODES = new Set([
  'MENU_GENERATION_INVALID',
  'MENU_GENERATION_OUTPUT_TRUNCATED',
  'MENU_GENERATION_TIMEOUT',
  'MENU_GENERATION_UNAVAILABLE',
  'GENERATION_INTERRUPTED',
  'GENERATION_FAILED',
  'GENERATION_SAVE_FAILED',
]);

export function getWorkflowRetryAction(error: StrategyWorkflowError): WorkflowRetryAction {
  if (error.kind === 'stale' || error.requiresNewPreview) {
    return 'build_new_preview';
  }
  if (error.code === 'PROFILE_STALE') {
    return 'reload_profile';
  }
  if (error.requiresProfileAction || error.kind === 'validation') {
    return 'open_profile';
  }
  if (error.kind === 'authentication') {
    return 'restart_app';
  }
  if (
    error.retryable ||
    error.kind === 'rate_limited' ||
    error.kind === 'service_unavailable' ||
    GENERATION_RETRY_CODES.has(error.code)
  ) {
    return 'retry_same_request';
  }
  return 'none';
}

export function getWorkflowRetryActionLabel(
  action: WorkflowRetryAction,
  error?: StrategyWorkflowError,
): string | null {
  if (
    action === 'retry_same_request' &&
    error &&
    GENERATION_RETRY_CODES.has(error.code)
  ) {
    return 'Попробовать ещё раз';
  }
  return RETRY_LABELS[action];
}
