import { describe, expect, it } from 'vitest';

import {
  canRetryResource,
  createInitialAsyncResourceState,
  getResourceRetryDescriptor,
  hasResourceData,
  isInitialLoadError,
  isInitialLoading,
  isRefreshError,
  isRefreshing,
} from '@/features/async-resource';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';
import type { AsyncResourceState } from '@/features/async-resource';

const workflowError = classifyStrategyWorkflowError(new Error('x'));

describe('asyncResourceSelectors', () => {
  it('detects initial loading', () => {
    expect(isInitialLoading(createInitialAsyncResourceState())).toBe(true);
    const loading: AsyncResourceState<string> = {
      status: 'loading',
      data: null,
      error: null,
      lastUpdatedAt: null,
      requestId: 1,
    };
    expect(isInitialLoading(loading)).toBe(true);
  });

  it('detects refreshing and has data', () => {
    const refreshing: AsyncResourceState<string> = {
      status: 'refreshing',
      data: 'keep',
      error: null,
      lastUpdatedAt: 1,
      requestId: 2,
    };
    expect(isRefreshing(refreshing)).toBe(true);
    expect(hasResourceData(refreshing)).toBe(true);
  });

  it('distinguishes initial vs refresh error', () => {
    const initial: AsyncResourceState<string> = {
      status: 'error',
      data: null,
      error: workflowError,
      lastUpdatedAt: null,
      requestId: 1,
    };
    const refresh: AsyncResourceState<string> = {
      status: 'error',
      data: 'old',
      error: workflowError,
      lastUpdatedAt: 2,
      requestId: 2,
    };
    expect(isInitialLoadError(initial)).toBe(true);
    expect(isRefreshError(initial)).toBe(false);
    expect(isInitialLoadError(refresh)).toBe(false);
    expect(isRefreshError(refresh)).toBe(true);
  });

  it('retry descriptor enables only on error and not while refreshing', () => {
    const errorState: AsyncResourceState<string> = {
      status: 'error',
      data: 'old',
      error: workflowError,
      lastUpdatedAt: 1,
      requestId: 3,
    };
    expect(canRetryResource(errorState)).toBe(true);
    const descriptor = getResourceRetryDescriptor(errorState);
    expect(descriptor.action).toBe('reload_resource');
    expect(descriptor.label).toBe('Повторить');
    expect(descriptor.enabled).toBe(true);

    const refreshing: AsyncResourceState<string> = {
      status: 'refreshing',
      data: 'old',
      error: null,
      lastUpdatedAt: 1,
      requestId: 4,
    };
    expect(getResourceRetryDescriptor(refreshing).enabled).toBe(false);
  });
});
