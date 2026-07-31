import { describe, expect, it } from 'vitest';

import {
  shouldLoadResourceOnMount,
  RESOURCE_FRESHNESS_POLICIES,
  asyncResourceReducer,
  createInitialAsyncResourceState,
} from '@/features/async-resource';
import type { ProfileServerState } from '@/features/profile/ProfileProvider';
import { normalizeProfile } from '@/features/profile/normalizeProfile';
import { INITIAL_STRATEGY_INPUTS_STATE } from '@/features/strategy-inputs/strategyInputsState';
import type { MenuPlan } from '@/types/menu';

function server(revision: number): ProfileServerState {
  const profile = normalizeProfile({
    user_id: 1,
    first_name: 'T',
    days: 5,
    budget: 3000,
    proteins: ['chicken'],
    goal: 'home',
    meal_types: ['breakfast'],
    meals_per_day: 1,
    persons: 1,
    cooktime: 'medium',
    dietary_constraints: [],
    store: 'any',
    updated_at: '2026-01-01T00:00:00Z',
  });
  return { profile, revision, updatedAt: profile.updated_at };
}

const menu: MenuPlan = {
  summary: 'x',
  plan_start_date: '2026-07-13',
  strategy_id: 's',
  total_cost: 1,
  days_plan: [],
  recipes: [],
  basket: [],
};

describe('profileFreshness', () => {
  it('fresh mount skips GET decision', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<ProfileServerState>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: server(1), now: 1000 },
    );
    expect(
      shouldLoadResourceOnMount(ready, RESOURCE_FRESHNESS_POLICIES.profile, 1000 + 60_000),
    ).toBe(false);
  });

  it('stale mount requests refresh', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<ProfileServerState>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: server(1), now: 1000 },
    );
    expect(
      shouldLoadResourceOnMount(
        ready,
        RESOURCE_FRESHNESS_POLICIES.profile,
        1000 + RESOURCE_FRESHNESS_POLICIES.profile.staleAfterMs,
      ),
    ).toBe(true);
  });

  it('dirty draft snapshot preserved across refresh failure', () => {
    const draft = { dirty: true, days: 9 };
    const draftBaseRevision = 3;
    let resource = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<ProfileServerState>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: server(3), now: 1000 },
    );
    resource = asyncResourceReducer(resource, { type: 'refresh_started', requestId: 2 });
    resource = asyncResourceReducer(resource, {
      type: 'refresh_failed',
      requestId: 2,
      error: {
        kind: 'retryable',
        code: 'X',
        message: 'down',
        fieldErrors: [],
        retryable: true,
        requiresNewPreview: false,
        requiresProfileAction: false,
        staleReason: null,
        requestId: null,
        originalStatus: 503,
      },
    });
    expect(resource.data?.revision).toBe(3);
    expect(draft).toEqual({ dirty: true, days: 9 });
    expect(draftBaseRevision).toBe(3);
    expect(menu.strategy_id).toBe('s');
    expect(INITIAL_STRATEGY_INPUTS_STATE.revision).toBe(0);
  });
});
