import type { StrategyWorkflowError } from '@/features/strategy-workflow/types';

export type AsyncResourceStatus =
  | 'idle'
  | 'loading'
  | 'ready'
  | 'refreshing'
  | 'error';

/**
 * Discriminated async resource state.
 * `error` + `data != null` means refresh failure with preserved payload.
 */
export type AsyncResourceState<T> =
  | {
      status: 'idle';
      data: null;
      error: null;
      lastUpdatedAt: null;
      requestId: number;
    }
  | {
      status: 'loading';
      data: null;
      error: null;
      lastUpdatedAt: null;
      requestId: number;
    }
  | {
      status: 'ready';
      data: T;
      error: null;
      lastUpdatedAt: number;
      requestId: number;
    }
  | {
      status: 'refreshing';
      data: T;
      error: null;
      lastUpdatedAt: number;
      requestId: number;
    }
  | {
      status: 'error';
      data: T | null;
      error: StrategyWorkflowError;
      lastUpdatedAt: number | null;
      requestId: number;
    };

export function createInitialAsyncResourceState<T>(
  requestId = 0,
): AsyncResourceState<T> {
  return {
    status: 'idle',
    data: null,
    error: null,
    lastUpdatedAt: null,
    requestId,
  };
}
