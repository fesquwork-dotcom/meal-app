import { describe, expect, it } from 'vitest';

import {
  asyncResourceReducer,
  createInitialAsyncResourceState,
  shouldLoadResourceOnMount,
  RESOURCE_FRESHNESS_POLICIES,
} from '@/features/async-resource';
import type { MemorySignalsList } from '@/hooks/useMemorySignals';
import type { MemorySignal } from '@/types/memory';

const signal = (id: string): MemorySignal => ({
  id,
  type: 'x',
  label: id,
  status: 'observed',
  evidence_count: 1,
  confidence: 0.5,
});

describe('memoryFreshness', () => {
  it('fresh cache hit skips mount load', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<MemorySignalsList>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: [signal('a')], now: 1000 },
    );
    expect(
      shouldLoadResourceOnMount(ready, RESOURCE_FRESHNESS_POLICIES.memory, 1000 + 10_000),
    ).toBe(false);
  });

  it('stale refresh keeps cards while refreshing', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<MemorySignalsList>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: [signal('a')], now: 1000 },
    );
    const refreshing = asyncResourceReducer(ready, {
      type: 'refresh_started',
      requestId: 2,
    });
    expect(refreshing.data).toHaveLength(1);
    expect(refreshing.status).toBe('refreshing');
  });

  it('mutation success marks list fresh via new lastUpdatedAt', () => {
    const afterMutation = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<MemorySignalsList>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: [signal('b')], now: 5000 },
    );
    expect(afterMutation.lastUpdatedAt).toBe(5000);
    expect(
      shouldLoadResourceOnMount(
        afterMutation,
        RESOURCE_FRESHNESS_POLICIES.memory,
        5000 + 10_000,
      ),
    ).toBe(false);
  });
});
