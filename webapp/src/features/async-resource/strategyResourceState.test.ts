import { describe, expect, it } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';

import {
  asyncResourceReducer,
  createInitialAsyncResourceState,
} from '@/features/async-resource';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';
import type { CurrentStrategyResponse, StrategyByIdResponse } from '@/types/strategy';

function axiosError(status: number, code: string) {
  return new AxiosError('x', undefined, undefined, undefined, {
    status,
    data: { code, message: 'backend' },
    headers: {},
    statusText: 'Error',
    config: { headers: new AxiosHeaders() },
  });
}

const noneCurrent: CurrentStrategyResponse = {
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

describe('strategyResourceState', () => {
  it('current status:none is ready data', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<CurrentStrategyResponse>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: noneCurrent, now: 1 },
    );
    expect(ready.status).toBe('ready');
    expect(ready.data?.status).toBe('none');
  });

  it('active strategy is ready', () => {
    const active: CurrentStrategyResponse = {
      ...noneCurrent,
      status: 'active',
      strategy_id: 's1',
    };
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<CurrentStrategyResponse>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: active, now: 1 },
    );
    expect(ready.data?.strategy_id).toBe('s1');
  });

  it('by-ID success', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<StrategyByIdResponse>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: byId, now: 1 },
    );
    expect(ready.data?.strategy_id).toBe('s1');
  });

  it('initial 404 is error with null data', () => {
    const failed = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<StrategyByIdResponse>(), {
        type: 'load_started',
        requestId: 1,
      }),
      {
        type: 'load_failed',
        requestId: 1,
        error: classifyStrategyWorkflowError(axiosError(404, 'STRATEGY_NOT_FOUND')),
      },
    );
    expect(failed.data).toBeNull();
    expect(failed.error?.kind).toBe('not_found');
  });

  it('refresh 503 preserves old data', () => {
    let state = createInitialAsyncResourceState<StrategyByIdResponse>();
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 1 });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 1,
      data: byId,
      now: 1,
    });
    state = asyncResourceReducer(state, { type: 'refresh_started', requestId: 2 });
    state = asyncResourceReducer(state, {
      type: 'refresh_failed',
      requestId: 2,
      error: classifyStrategyWorkflowError(axiosError(503, 'SERVICE_UNAVAILABLE')),
    });
    expect(state.data?.strategy_id).toBe('s1');
    expect(state.error?.kind).toBe('service_unavailable');
  });

  it('refresh 404 clears data (authoritative)', () => {
    // Mirrors useStrategyById policy: not_found clears cached strategy.
    let state = createInitialAsyncResourceState<StrategyByIdResponse>();
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 1 });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 1,
      data: byId,
      now: 1,
    });
    state = asyncResourceReducer(state, { type: 'refresh_started', requestId: 2 });
    const notFound = classifyStrategyWorkflowError(axiosError(404, 'STRATEGY_NOT_FOUND'));
    state = {
      status: 'error',
      data: notFound.kind === 'not_found' ? null : state.data,
      error: notFound,
      lastUpdatedAt: notFound.kind === 'not_found' ? null : state.lastUpdatedAt,
      requestId: 2,
    };
    expect(state.data).toBeNull();
  });

  it('late response ignored', () => {
    let state = createInitialAsyncResourceState<CurrentStrategyResponse>();
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 1 });
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 2 });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 2,
      data: noneCurrent,
      now: 2,
    });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 1,
      data: { ...noneCurrent, status: 'active', strategy_id: 'old' },
      now: 1,
    });
    expect(state.data?.status).toBe('none');
  });
});
