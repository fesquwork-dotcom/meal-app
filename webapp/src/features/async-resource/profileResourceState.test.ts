import { describe, expect, it } from 'vitest';

import {
  asyncResourceReducer,
  createInitialAsyncResourceState,
} from '@/features/async-resource';
import type { ProfileServerState } from '@/features/profile/ProfileProvider';
import { normalizeProfile } from '@/features/profile/normalizeProfile';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';
import { INITIAL_STRATEGY_INPUTS_STATE } from '@/features/strategy-inputs/strategyInputsState';
import type { MenuPlan } from '@/types/menu';

function profile(revisionHint = 1): ProfileServerState {
  const p = normalizeProfile({
    user_id: 1,
    first_name: 'Test',
    days: 5,
    budget: 3000,
    proteins: ['chicken'],
    goal: 'home',
    meal_types: ['breakfast', 'lunch', 'dinner'],
    meals_per_day: 3,
    persons: 2,
    cooktime: 'medium',
    dietary_constraints: [],
    store: 'any',
    updated_at: '2026-01-01T00:00:00Z',
  });
  return { profile: p, revision: revisionHint, updatedAt: p.updated_at };
}

const sampleMenu: MenuPlan = {
  summary: 'План',
  plan_start_date: '2026-07-13',
  strategy_id: 'strategy-res',
  total_cost: 1000,
  days_plan: [],
  recipes: [],
  basket: [],
};

describe('profileResourceState', () => {
  it('initial load success', () => {
    let state = createInitialAsyncResourceState<ProfileServerState>();
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 1 });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 1,
      data: profile(1),
      now: 10,
    });
    expect(state.status).toBe('ready');
    expect(state.data?.revision).toBe(1);
  });

  it('missing profile can be represented as ready default payload', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<ProfileServerState>(), {
        type: 'load_started',
        requestId: 1,
      }),
      {
        type: 'load_succeeded',
        requestId: 1,
        data: profile(0),
        now: 1,
      },
    );
    expect(ready.status).toBe('ready');
    expect(ready.data?.revision).toBe(0);
  });

  it('refresh failure preserves server data and does not clear draft marker', () => {
    const draft = { dirty: true, days: 9 };
    let state = createInitialAsyncResourceState<ProfileServerState>();
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 1 });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 1,
      data: profile(3),
      now: 10,
    });
    state = asyncResourceReducer(state, { type: 'refresh_started', requestId: 2 });
    state = asyncResourceReducer(state, {
      type: 'refresh_failed',
      requestId: 2,
      error: classifyStrategyWorkflowError(new Error('down')),
    });
    expect(state.data?.revision).toBe(3);
    expect(draft).toEqual({ dirty: true, days: 9 });
  });

  it('action error is separate from resource error', () => {
    const resource = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<ProfileServerState>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: profile(1), now: 1 },
    );
    const actionError = classifyStrategyWorkflowError(new Error('save failed'));
    expect(resource.error).toBeNull();
    expect(actionError).toBeTruthy();
    expect(resource.status).toBe('ready');
  });

  it('late older revision is ignored by request race', () => {
    let state = createInitialAsyncResourceState<ProfileServerState>();
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 1 });
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 2 });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 2,
      data: profile(5),
      now: 2,
    });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 1,
      data: profile(2),
      now: 1,
    });
    expect(state.data?.revision).toBe(5);
  });

  it('resource failure does not bump coordinator or clear MenuPlan', () => {
    const before = structuredClone(sampleMenu);
    const rev = INITIAL_STRATEGY_INPUTS_STATE.revision;
    asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<ProfileServerState>(), {
        type: 'load_started',
        requestId: 1,
      }),
      {
        type: 'load_failed',
        requestId: 1,
        error: classifyStrategyWorkflowError(new Error('fail')),
      },
    );
    expect(sampleMenu).toEqual(before);
    expect(INITIAL_STRATEGY_INPUTS_STATE.revision).toBe(rev);
  });
});
