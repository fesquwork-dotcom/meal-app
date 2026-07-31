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
  if (error.retryable || error.kind === 'rate_limited' || error.kind === 'service_unavailable') {
    return 'retry_same_request';
  }
  return 'none';
}

export function getWorkflowRetryActionLabel(action: WorkflowRetryAction): string | null {
  return RETRY_LABELS[action];
}
