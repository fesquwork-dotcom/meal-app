import { describe, expect, it } from 'vitest';

import {
  workflowFailure,
  workflowSuccess,
} from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import { AxiosError, AxiosHeaders } from 'axios';

describe('WorkflowResult', () => {
  it('wraps success payload', () => {
    const result = workflowSuccess({ menuPlanId: '1' });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.menuPlanId).toBe('1');
    }
  });

  it('wraps classified failure without boolean-only shape', () => {
    const err = new AxiosError(
      'fail',
      undefined,
      undefined,
      undefined,
      {
        status: 502,
        data: { code: 'STRATEGY_SAVE_FAILED', message: 'db' },
        headers: {},
        statusText: 'Bad Gateway',
        config: { headers: new AxiosHeaders() },
      },
    );
    const result = workflowFailure(err);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.retryable).toBe(true);
      expect(result.error.code).toBe('STRATEGY_SAVE_FAILED');
    }
  });
});
