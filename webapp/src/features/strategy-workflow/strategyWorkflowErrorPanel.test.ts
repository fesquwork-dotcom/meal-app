import { describe, expect, it } from 'vitest';

import {
  getWorkflowRetryAction,
  getWorkflowRetryActionLabel,
} from '@/features/strategy-workflow/strategyWorkflowRetryAction';
import type { StrategyWorkflowError } from '@/features/strategy-workflow/types';
import type { StrategyWorkflowErrorPanelVariant } from '@/features/strategy-workflow/StrategyWorkflowErrorPanel';

function viewModel(
  error: StrategyWorkflowError,
  options: {
    variant?: StrategyWorkflowErrorPanelVariant;
    onRetry?: () => void;
    onOpenProfile?: () => void;
    onReloadProfile?: () => void;
    onRestart?: () => void;
    onDismiss?: () => void;
    showRequestId?: boolean;
  } = {},
) {
  const action = getWorkflowRetryAction(error);
  const variant = options.variant ?? 'full';
  const canInvoke =
    ((action === 'retry_same_request' || action === 'build_new_preview') &&
      Boolean(options.onRetry)) ||
    (action === 'open_profile' && Boolean(options.onOpenProfile)) ||
    (action === 'reload_profile' && Boolean(options.onReloadProfile)) ||
    (action === 'restart_app' && Boolean(options.onRestart));
  return {
    variant,
    message: error.message,
    fieldMessages: error.fieldErrors.map((item) => item.message),
    action,
    actionLabel: getWorkflowRetryActionLabel(action),
    showActionButton:
      variant !== 'inline' && Boolean(getWorkflowRetryActionLabel(action)) && canInvoke,
    showDismiss: Boolean(options.onDismiss) && variant !== 'inline',
    requestIdLine:
      options.showRequestId && error.requestId ? `Код обращения: ${error.requestId}` : null,
  };
}

const validationError: StrategyWorkflowError = {
  kind: 'validation',
  code: 'REQUEST_VALIDATION_ERROR',
  message: 'Проверьте введённые данные.',
  fieldErrors: [
    { field: 'profile.proteins', code: 'PROFILE_PROTEIN_REQUIRED', message: 'Выберите белок.' },
    { field: 'unknown_field', code: 'X', message: 'Другая ошибка' },
  ],
  retryable: false,
  requiresNewPreview: false,
  requiresProfileAction: true,
  staleReason: null,
  requestId: 'req_abc',
  originalStatus: 422,
};

describe('StrategyWorkflowErrorPanel view model', () => {
  it('full variant exposes message, fields, action label and optional request id', () => {
    const vm = viewModel(validationError, {
      variant: 'full',
      onOpenProfile: () => undefined,
      showRequestId: true,
    });
    expect(vm.variant).toBe('full');
    expect(vm.fieldMessages).toEqual(['Выберите белок.', 'Другая ошибка']);
    expect(vm.action).toBe('open_profile');
    expect(vm.actionLabel).toBe('Открыть профиль');
    expect(vm.showActionButton).toBe(true);
    expect(vm.requestIdLine).toContain('req_abc');
  });

  it('compact variant still shows action when callback present', () => {
    const vm = viewModel(
      {
        ...validationError,
        kind: 'retryable',
        code: 'CLIENT_TIMEOUT',
        fieldErrors: [],
        retryable: true,
        requiresProfileAction: false,
        requestId: null,
      },
      { variant: 'compact', onRetry: () => undefined },
    );
    expect(vm.variant).toBe('compact');
    expect(vm.showActionButton).toBe(true);
    expect(vm.actionLabel).toBe('Повторить');
  });

  it('inline variant hides action buttons even when callbacks exist', () => {
    const vm = viewModel(validationError, {
      variant: 'inline',
      onOpenProfile: () => undefined,
      onDismiss: () => undefined,
    });
    expect(vm.variant).toBe('inline');
    expect(vm.showActionButton).toBe(false);
    expect(vm.showDismiss).toBe(false);
  });

  it('handles empty field list', () => {
    const vm = viewModel({
      kind: 'retryable',
      code: 'CLIENT_TIMEOUT',
      message: 'timeout',
      fieldErrors: [],
      retryable: true,
      requiresNewPreview: false,
      requiresProfileAction: false,
      staleReason: null,
      requestId: null,
      originalStatus: null,
    });
    expect(vm.fieldMessages).toEqual([]);
    expect(vm.actionLabel).toBe('Повторить');
  });

  it('no callback → no action button', () => {
    const vm = viewModel(validationError, { variant: 'full' });
    expect(vm.showActionButton).toBe(false);
  });
});
