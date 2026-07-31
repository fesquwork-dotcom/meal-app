import { describe, expect, it } from 'vitest';

import { getWorkflowRetryAction } from '@/features/strategy-workflow/strategyWorkflowRetryAction';
import type { StrategyWorkflowError } from '@/features/strategy-workflow/types';

function error(partial: Partial<StrategyWorkflowError>): StrategyWorkflowError {
  return {
    kind: 'unknown',
    code: 'X',
    message: 'm',
    fieldErrors: [],
    retryable: false,
    requiresNewPreview: false,
    requiresProfileAction: false,
    staleReason: null,
    requestId: null,
    originalStatus: null,
    ...partial,
  };
}

describe('getWorkflowRetryAction', () => {
  it('maps stale to build_new_preview', () => {
    expect(
      getWorkflowRetryAction(
        error({
          kind: 'stale',
          requiresNewPreview: true,
          staleReason: 'server_stale_profile',
        }),
      ),
    ).toBe('build_new_preview');
  });

  it('maps timeout/retryable to retry_same_request', () => {
    expect(getWorkflowRetryAction(error({ kind: 'retryable', retryable: true }))).toBe(
      'retry_same_request',
    );
  });

  it('maps invalid profile to open_profile', () => {
    expect(
      getWorkflowRetryAction(
        error({ kind: 'validation', requiresProfileAction: true, code: 'PROFILE_PROTEIN_REQUIRED' }),
      ),
    ).toBe('open_profile');
  });

  it('maps PROFILE_STALE to reload_profile', () => {
    expect(getWorkflowRetryAction(error({ kind: 'conflict', code: 'PROFILE_STALE' }))).toBe(
      'reload_profile',
    );
  });

  it('maps auth to restart_app and fatal to none', () => {
    expect(getWorkflowRetryAction(error({ kind: 'authentication' }))).toBe('restart_app');
    expect(getWorkflowRetryAction(error({ kind: 'fatal' }))).toBe('none');
  });
});
