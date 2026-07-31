import { describe, expect, it } from 'vitest';

import {
  getStrategyWorkflowCodeMessage,
  resolveStrategyWorkflowMessage,
} from '@/features/strategy-workflow/strategyWorkflowErrorMessages';

describe('strategyWorkflowErrorMessages', () => {
  it('returns centralized copy for known codes', () => {
    expect(getStrategyWorkflowCodeMessage('STRATEGY_PREVIEW_STALE_PROFILE')).toContain('другой сессии');
    expect(getStrategyWorkflowCodeMessage('BEHAVIOR_SERVICE_UNAVAILABLE')).toContain('наблюдения');
    expect(getStrategyWorkflowCodeMessage('REPLACEMENT_FAILED')).toContain('заменить');
  });

  it('prefers known frontend message over technical backend text', () => {
    const message = resolveStrategyWorkflowMessage({
      code: 'CONFLICT_NOT_FOUND',
      kind: 'conflict',
      backendMessage: 'Traceback SQLAlchemy stack',
    });
    expect(message).toContain('противоречие');
  });

  it('falls back to kind generic when unknown', () => {
    const message = resolveStrategyWorkflowMessage({
      code: 'SOME_NEW_CODE',
      kind: 'retryable',
      backendMessage: null,
    });
    expect(message).toContain('Временная ошибка');
  });
});
