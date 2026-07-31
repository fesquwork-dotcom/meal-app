import { describe, expect, it } from 'vitest';

import {
  asyncResourceReducer,
  createInitialAsyncResourceState,
} from '@/features/async-resource';
import type { MemorySignalsList } from '@/hooks/useMemorySignals';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';
import type { MemorySignal } from '@/types/memory';

const signal = (id: string): MemorySignal => ({
  id,
  type: 'ingredient_exclusion',
  label: id,
  status: 'observed',
  evidence_count: 1,
  confidence: 0.5,
});

describe('memoryResourceState', () => {
  it('initial empty list is ready', () => {
    const ready = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<MemorySignalsList>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: [], now: 1 },
    );
    expect(ready.status).toBe('ready');
    expect(ready.data).toEqual([]);
  });

  it('initial load error has null data', () => {
    const failed = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<MemorySignalsList>(), {
        type: 'load_started',
        requestId: 1,
      }),
      {
        type: 'load_failed',
        requestId: 1,
        error: classifyStrategyWorkflowError(new Error('fail')),
      },
    );
    expect(failed.data).toBeNull();
  });

  it('refresh error preserves signals', () => {
    let state = createInitialAsyncResourceState<MemorySignalsList>();
    state = asyncResourceReducer(state, { type: 'load_started', requestId: 1 });
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: 1,
      data: [signal('ms_1')],
      now: 1,
    });
    state = asyncResourceReducer(state, { type: 'refresh_started', requestId: 2 });
    state = asyncResourceReducer(state, {
      type: 'refresh_failed',
      requestId: 2,
      error: classifyStrategyWorkflowError(new Error('down')),
    });
    expect(state.data).toHaveLength(1);
    expect(state.status).toBe('error');
  });

  it('action error does not change resource status', () => {
    const resource = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<MemorySignalsList>(), {
        type: 'load_started',
        requestId: 1,
      }),
      { type: 'load_succeeded', requestId: 1, data: [signal('ms_1')], now: 1 },
    );
    const actionError = classifyStrategyWorkflowError(new Error('promote failed'));
    expect(resource.status).toBe('ready');
    expect(actionError.kind).toBeTruthy();
  });

  it('local mutation success can replace list without reload failure', () => {
    let state = asyncResourceReducer(
      asyncResourceReducer(createInitialAsyncResourceState<MemorySignalsList>(), {
        type: 'load_started',
        requestId: 1,
      }),
      {
        type: 'load_succeeded',
        requestId: 1,
        data: [signal('ms_1'), signal('ms_2')],
        now: 1,
      },
    );
    state = asyncResourceReducer(state, {
      type: 'load_succeeded',
      requestId: state.requestId,
      data: [signal('ms_2')],
      now: 2,
    });
    expect(state.data?.map((item) => item.id)).toEqual(['ms_2']);
  });
});
