import { describe, expect, it } from 'vitest';

import { shouldLoadResourceOnMount } from '@/features/async-resource/resourceFreshness';
import {
  createInitialAsyncResourceState,
  asyncResourceReducer,
  RESOURCE_FRESHNESS_POLICIES,
} from '@/features/async-resource';
import type { ResourceFreshnessPolicy } from '@/features/async-resource/resourceFreshnessPolicy';

function readyAt(now: number) {
  return asyncResourceReducer(
    asyncResourceReducer(createInitialAsyncResourceState<string[]>(), {
      type: 'load_started',
      requestId: 1,
    }),
    { type: 'load_succeeded', requestId: 1, data: [], now },
  );
}

describe('resourceFreshnessPolicy / mount', () => {
  it('exposes per-resource policies', () => {
    expect(RESOURCE_FRESHNESS_POLICIES.profile.staleAfterMs).toBe(5 * 60_000);
    expect(RESOURCE_FRESHNESS_POLICIES.memory.refreshOnMount).toBe('if_stale');
    expect(RESOURCE_FRESHNESS_POLICIES.behavior.staleAfterMs).toBe(2 * 60_000);
    expect(RESOURCE_FRESHNESS_POLICIES.strategyById.staleAfterMs).toBe(5 * 60_000);
  });

  it('no data → load', () => {
    expect(
      shouldLoadResourceOnMount(createInitialAsyncResourceState(), RESOURCE_FRESHNESS_POLICIES.memory, 0),
    ).toBe(true);
  });

  it('fresh → no load for if_stale', () => {
    const state = readyAt(1000);
    expect(
      shouldLoadResourceOnMount(state, RESOURCE_FRESHNESS_POLICIES.memory, 1000 + 30_000),
    ).toBe(false);
  });

  it('stale → refresh for if_stale', () => {
    const state = readyAt(1000);
    expect(
      shouldLoadResourceOnMount(
        state,
        RESOURCE_FRESHNESS_POLICIES.memory,
        1000 + RESOURCE_FRESHNESS_POLICIES.memory.staleAfterMs,
      ),
    ).toBe(true);
  });

  it('always → refresh even when fresh', () => {
    const always: ResourceFreshnessPolicy = {
      staleAfterMs: 60_000,
      refreshOnMount: 'always',
    };
    expect(shouldLoadResourceOnMount(readyAt(1000), always, 1010)).toBe(true);
  });

  it('never → no refresh when data exists', () => {
    const never: ResourceFreshnessPolicy = {
      staleAfterMs: 1,
      refreshOnMount: 'never',
    };
    expect(shouldLoadResourceOnMount(readyAt(1000), never, 999_999)).toBe(false);
  });

  it('pending load does not start another', () => {
    const loading = asyncResourceReducer(createInitialAsyncResourceState(), {
      type: 'load_started',
      requestId: 1,
    });
    expect(shouldLoadResourceOnMount(loading, RESOURCE_FRESHNESS_POLICIES.profile, 0)).toBe(false);
  });
});
