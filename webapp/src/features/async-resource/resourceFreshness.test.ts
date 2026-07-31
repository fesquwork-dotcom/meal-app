import { describe, expect, it } from 'vitest';

import {
  getResourceFreshness,
  selectResourceFreshness,
} from '@/features/async-resource/resourceFreshness';
import {
  createInitialAsyncResourceState,
  asyncResourceReducer,
} from '@/features/async-resource';
import type { ResourceFreshnessPolicy } from '@/features/async-resource/resourceFreshnessPolicy';

const policy: ResourceFreshnessPolicy = {
  staleAfterMs: 60_000,
  refreshOnMount: 'if_stale',
};

describe('resourceFreshness', () => {
  it('null lastUpdatedAt → unknown', () => {
    expect(getResourceFreshness(null, policy, 1000)).toBe('unknown');
  });

  it('before threshold → fresh', () => {
    expect(getResourceFreshness(1000, policy, 1000 + 59_999)).toBe('fresh');
  });

  it('exact threshold → stale (age >= staleAfterMs)', () => {
    expect(getResourceFreshness(1000, policy, 1000 + 60_000)).toBe('stale');
  });

  it('after threshold → stale', () => {
    expect(getResourceFreshness(1000, policy, 1000 + 60_001)).toBe('stale');
  });

  it('selectResourceFreshness uses state lastUpdatedAt', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<string>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: 'x', now: 1000 },
    );
    expect(selectResourceFreshness(ready, policy, 1000 + 10)).toBe('fresh');
    expect(selectResourceFreshness(ready, policy, 1000 + 60_000)).toBe('stale');
  });
});
