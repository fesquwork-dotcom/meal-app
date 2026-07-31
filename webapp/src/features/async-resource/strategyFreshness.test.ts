import { describe, expect, it } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';

import {
  asyncResourceReducer,
  createInitialAsyncResourceState,
  shouldLoadResourceOnMount,
  RESOURCE_FRESHNESS_POLICIES,
} from '@/features/async-resource';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';
import type { CurrentStrategyResponse, StrategyByIdResponse } from '@/types/strategy';

const none: CurrentStrategyResponse = {
  status: 'none',
  strategy_id: null,
  plan_start_date: null,
  plan_end_date: null,
  strategy: null,
  explanation: null,
};

const byId: StrategyByIdResponse = {
  strategy_id: 's1',
  status: 'active',
  plan_start_date: '2026-07-13',
  plan_end_date: '2026-07-19',
  strategy: {
    strategy_version: 1,
    goal: 'home',
    days: 5,
    budget: 3000,
    meal_types: ['breakfast'],
    cook_days: [1],
    shopping_days: [1],
    leftovers_enabled: false,
    repeat_breakfasts: false,
    repeat_lunches: false,
    repeat_dinners: false,
    preferred_proteins: ['chicken'],
    excluded_products: [],
    cooking_time_limit: 45,
  },
  explanation: null,
};

function axiosError(status: number, code: string) {
  return new AxiosError('x', undefined, undefined, undefined, {
    status,
    data: { code, message: 'backend' },
    headers: {},
    statusText: 'Error',
    config: { headers: new AxiosHeaders() },
  });
}

describe('strategyFreshness', () => {
  it('current stale refresh required', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<CurrentStrategyResponse>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: none, now: 1000 },
    );
    expect(ready.data?.status).toBe('none');
    expect(
      shouldLoadResourceOnMount(
        ready,
        RESOURCE_FRESHNESS_POLICIES.currentStrategy,
        1000 + RESOURCE_FRESHNESS_POLICIES.currentStrategy.staleAfterMs,
      ),
    ).toBe(true);
  });

  it('by-ID fresh cache hit', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<StrategyByIdResponse>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: byId, now: 1000 },
    );
    expect(
      shouldLoadResourceOnMount(ready, RESOURCE_FRESHNESS_POLICIES.strategyById, 1000 + 60_000),
    ).toBe(false);
  });

  it('404 clears cache; 503 preserves', () => {
    let state = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<StrategyByIdResponse>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: byId, now: 1000 },
    );
    state = asyncResourceReducer(state, { type: 'refresh_started', requestId: 2 });
    const preserved = asyncResourceReducer(state, {
      type: 'refresh_failed',
      requestId: 2,
      error: classifyStrategyWorkflowError(axiosError(503, 'SERVICE_UNAVAILABLE')),
    });
    expect(preserved.data?.strategy_id).toBe('s1');

    const notFound = classifyStrategyWorkflowError(axiosError(404, 'STRATEGY_NOT_FOUND'));
    const cleared = {
      status: 'error' as const,
      data: notFound.kind === 'not_found' ? null : preserved.data,
      error: notFound,
      lastUpdatedAt: null,
      requestId: 3,
    };
    expect(cleared.data).toBeNull();
  });
});
