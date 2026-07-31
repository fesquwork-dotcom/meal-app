import { describe, expect, it } from 'vitest';

import {
  asyncResourceReducer,
  createInitialAsyncResourceState,
} from '@/features/async-resource';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';

describe('resourceRaceProtection', () => {
  it('ignores late success from older request', () => {
    let state = createInitialAsyncResourceState<string>();
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 1 });
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 2 });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 2,
      data: 'second',
      now: 20,
    });
    const late = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 1,
      data: 'first',
      now: 10,
    });
    expect(late.data).toBe('second');
    expect(late.requestId).toBe(2);
  });

  it('ignores late failure from older request', () => {
    let state = createInitialAsyncResourceState<string>();
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 1 });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 1,
      data: 'ok',
      now: 1,
    });
    state = asyncResourceReducer(state, { type: 'refresh_started', requestId: 2 });
    state = asyncResourceReducer(state, {
      type: 'refresh_succeeded',
      requestId: 2,
      data: 'newer',
      now: 2,
    });
    const lateFail = asyncResourceReducer(state, {
      type: 'refresh_failed',
      requestId: 1,
      error: classifyStrategyWorkflowError(new Error('stale')),
    });
    expect(lateFail.status).toBe('ready');
    expect(lateFail.data).toBe('newer');
  });

  it('request 1 start, request 2 start, request 2 success, request 1 success late', () => {
    let state = createInitialAsyncResourceState<{ revision: number }>();
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 1 });
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 2 });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 2,
      data: { revision: 2 },
      now: 2,
    });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 1,
      data: { revision: 1 },
      now: 1,
    });
    expect(state.data?.revision).toBe(2);
  });
});
