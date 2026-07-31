import { describe, expect, it } from 'vitest';

import {
  asyncResourceReducer,
  buildAsyncResourceViewModel,
  createInitialAsyncResourceState,
  getResourceFreshness,
} from '@/features/async-resource';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';

const policy = { staleAfterMs: 60_000, refreshOnMount: 'if_stale' as const };

describe('staleCacheViewModel', () => {
  it('initial loader without data', () => {
    const loading = asyncResourceReducer(createInitialAsyncResourceState(), {
      type: 'load_started',
      requestId: 1,
    });
    const freshness = getResourceFreshness(loading.lastUpdatedAt, policy, 0);
    const vm = buildAsyncResourceViewModel(loading, freshness);
    expect(vm.showInitialLoader).toBe(true);
    expect(vm.showData).toBe(false);
    expect(vm.showFullError).toBe(false);
  });

  it('ready data hides loader', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<string>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: 'ok', now: 10 },
    );
    const vm = buildAsyncResourceViewModel(ready, 'fresh');
    expect(vm.showData).toBe(true);
    expect(vm.showInitialLoader).toBe(false);
    expect(vm.showRefreshingIndicator).toBe(false);
  });

  it('refreshing data shows indicator and keeps data', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<string>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: 'ok', now: 10 },
    );
    const refreshing = asyncResourceReducer(ready, {
      type: 'refresh_started',
      requestId: 2,
    });
    const vm = buildAsyncResourceViewModel(refreshing, 'stale');
    expect(vm.showData).toBe(true);
    expect(vm.showRefreshingIndicator).toBe(true);
    expect(vm.retryEnabled).toBe(false);
  });

  it('refresh error with data enables retry', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<string>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: 'ok', now: 10 },
    );
    const failed = asyncResourceReducer(
      asyncResourceReducer(ready, { type: 'refresh_started', requestId: 2 }),
      {
        type: 'refresh_failed',
        requestId: 2,
        error: classifyStrategyWorkflowError(new Error('down')),
      },
    );
    const vm = buildAsyncResourceViewModel(failed, 'stale');
    expect(vm.showRefreshError).toBe(true);
    expect(vm.showData).toBe(true);
    expect(vm.retryEnabled).toBe(true);
  });

  it('full error without data', () => {
    const failed = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState(), {
        type: 'load_started',
        requestId: 1,
      }),
      {
        type: 'load_failed',
        requestId: 1,
        error: classifyStrategyWorkflowError(new Error('fail')),
      },
    );
    const vm = buildAsyncResourceViewModel(failed, 'unknown');
    expect(vm.showFullError).toBe(true);
    expect(vm.showData).toBe(false);
  });
});
