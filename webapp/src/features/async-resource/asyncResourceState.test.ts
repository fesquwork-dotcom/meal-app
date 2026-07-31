import { describe, expect, it } from 'vitest';

import {
  asyncResourceReducer,
  createInitialAsyncResourceState,
  startResourceLoad,
} from '@/features/async-resource';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';

const err = () => classifyStrategyWorkflowError(new Error('boom'));

describe('asyncResourceReducer', () => {
  it('transitions idle → loading → ready', () => {
    const idle = createInitialAsyncResourceState<string[]>();
    const loading = asyncResourceReducer(idle, { type: 'load_started', requestId: 1 });
    expect(loading.status).toBe('loading');
    expect(loading.data).toBeNull();
    const ready = asyncResourceReducer(loading, {
      type: 'load_succeeded',
      requestId: 1,
      data: ['a'],
      now: 100,
    });
    expect(ready.status).toBe('ready');
    expect(ready.data).toEqual(['a']);
    expect(ready.lastUpdatedAt).toBe(100);
  });

  it('transitions loading → initial error with null data', () => {
    const loading = asyncResourceReducer(createInitialAsyncResourceState<number>(), {
      type: 'load_started',
      requestId: 1,
    });
    const failed = asyncResourceReducer(loading, {
      type: 'load_failed',
      requestId: 1,
      error: err(),
    });
    expect(failed.status).toBe('error');
    expect(failed.data).toBeNull();
  });

  it('ready → refreshing → ready', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<string>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: 'v1', now: 10 },
    );
    const refreshing = asyncResourceReducer(ready, {
      type: 'refresh_started',
      requestId: 2,
    });
    expect(refreshing.status).toBe('refreshing');
    expect(refreshing.data).toBe('v1');
    const next = asyncResourceReducer(refreshing, {
      type: 'refresh_succeeded',
      requestId: 2,
      data: 'v2',
      now: 20,
    });
    expect(next.status).toBe('ready');
    expect(next.data).toBe('v2');
  });

  it('refreshing → error keeps previous data', () => {
    const ready = asyncResourceReducer(createInitialAsyncResourceState<string[]>(), {
      type: 'load_started',
      requestId: 1,
    });
    const withData = asyncResourceReducer(ready, {
      type: 'load_succeeded',
      requestId: 1,
      data: ['old'],
      now: 5,
    });
    const refreshing = asyncResourceReducer(withData, {
      type: 'refresh_started',
      requestId: 2,
    });
    const failed = asyncResourceReducer(refreshing, {
      type: 'refresh_failed',
      requestId: 2,
      error: err(),
    });
    expect(failed.status).toBe('error');
    expect(failed.data).toEqual(['old']);
    expect(failed.lastUpdatedAt).toBe(5);
  });

  it('retry success clears error', () => {
    const failed = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<string>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_failed', requestId: 1, error: err() },
    );
    const retrying = asyncResourceReducer(failed, { type: 'load_started', requestId: 2 });
    const recovered = asyncResourceReducer(retrying, {
      type: 'load_succeeded',
      requestId: 2,
      data: 'ok',
      now: 30,
    });
    expect(recovered.status).toBe('ready');
    expect(recovered.error).toBeNull();
  });

  it('reset returns idle', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<string>(), {
        type: 'load_started',
        requestId: 3,
      }),
      { type: 'load_succeeded', requestId: 3, data: 'x', now: 1 },
    );
    const reset = asyncResourceReducer(ready, { type: 'reset' });
    expect(reset.status).toBe('idle');
    expect(reset.data).toBeNull();
    expect(reset.requestId).toBe(0);
  });

  it('empty array is ready success, not error', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<string[]>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: [], now: 1 },
    );
    expect(ready.status).toBe('ready');
    expect(ready.data).toEqual([]);
  });

  it('startResourceLoad chooses refresh when data exists', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<string>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: 'a', now: 1 },
    );
    const started = startResourceLoad(ready);
    expect(started.state.status).toBe('refreshing');
    expect(started.requestId).toBe(2);
  });
});
