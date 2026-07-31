import { createInitialAsyncResourceState } from '@/features/async-resource/types';
import type { AsyncResourceState } from '@/features/async-resource/types';
import type { StrategyWorkflowError } from '@/features/strategy-workflow/types';

export type AsyncResourceAction<T> =
  | { type: 'load_started'; requestId: number }
  | { type: 'load_succeeded'; requestId: number; data: T; now?: number }
  | { type: 'load_failed'; requestId: number; error: StrategyWorkflowError }
  | { type: 'refresh_started'; requestId: number }
  | { type: 'refresh_succeeded'; requestId: number; data: T; now?: number }
  | { type: 'refresh_failed'; requestId: number; error: StrategyWorkflowError }
  | { type: 'reset' };

function nextRequestId(state: AsyncResourceState<unknown>): number {
  return state.requestId + 1;
}

/** Allocates the next request id for a load/refresh start (caller may bump via reducer). */
export function allocateResourceRequestId<T>(state: AsyncResourceState<T>): number {
  return nextRequestId(state);
}

function isCurrentRequest<T>(
  state: AsyncResourceState<T>,
  requestId: number,
): boolean {
  return state.requestId === requestId;
}

function stamp(now?: number): number {
  return typeof now === 'number' ? now : Date.now();
}

/**
 * Generic async resource transitions with request-id race protection.
 * Out-of-order responses for stale requestIds are ignored.
 */
export function asyncResourceReducer<T>(
  state: AsyncResourceState<T>,
  action: AsyncResourceAction<T>,
): AsyncResourceState<T> {
  switch (action.type) {
    case 'reset':
      return createInitialAsyncResourceState<T>();

    case 'load_started':
      return {
        status: 'loading',
        data: null,
        error: null,
        lastUpdatedAt: null,
        requestId: action.requestId,
      };

    case 'refresh_started': {
      if (state.data === null) {
        return {
          status: 'loading',
          data: null,
          error: null,
          lastUpdatedAt: null,
          requestId: action.requestId,
        };
      }
      return {
        status: 'refreshing',
        data: state.data,
        error: null,
        lastUpdatedAt: state.lastUpdatedAt ?? stamp(),
        requestId: action.requestId,
      };
    }

    case 'load_succeeded':
    case 'refresh_succeeded': {
      if (!isCurrentRequest(state, action.requestId)) {
        return state;
      }
      return {
        status: 'ready',
        data: action.data,
        error: null,
        lastUpdatedAt: stamp(action.now),
        requestId: action.requestId,
      };
    }

    case 'load_failed': {
      if (!isCurrentRequest(state, action.requestId)) {
        return state;
      }
      return {
        status: 'error',
        data: null,
        error: action.error,
        lastUpdatedAt: null,
        requestId: action.requestId,
      };
    }

    case 'refresh_failed': {
      if (!isCurrentRequest(state, action.requestId)) {
        return state;
      }
      return {
        status: 'error',
        data: state.data,
        error: action.error,
        lastUpdatedAt: state.lastUpdatedAt,
        requestId: action.requestId,
      };
    }

    default:
      return state;
  }
}

export function startResourceLoad<T>(
  state: AsyncResourceState<T>,
): { state: AsyncResourceState<T>; requestId: number } {
  const requestId = allocateResourceRequestId(state);
  const mode = state.data !== null ? 'refresh' : 'load';
  return {
    requestId,
    state: asyncResourceReducer(
      state,
      mode === 'refresh'
        ? { type: 'refresh_started', requestId }
        : { type: 'load_started', requestId },
    ),
  };
}

export function logResourceLoadStarted(resource: string, requestId: number): void {
  if (import.meta.env.DEV) {
    console.info('resource_load_started', { resource, requestId });
  }
}

export function logResourceLoadSucceeded(resource: string, requestId: number): void {
  if (import.meta.env.DEV) {
    console.info('resource_load_succeeded', { resource, requestId });
  }
}

export function logResourceLoadFailed(
  resource: string,
  requestId: number,
  error: StrategyWorkflowError,
  hadPreviousData: boolean,
): void {
  if (import.meta.env.DEV) {
    console.info(hadPreviousData ? 'resource_refresh_failed' : 'resource_load_failed', {
      resource,
      requestId,
      kind: error.kind,
      code: error.code,
      hadPreviousData,
    });
  }
}

export function logResourceResponseIgnored(
  resource: string,
  requestId: number,
  currentRequestId: number,
): void {
  if (import.meta.env.DEV) {
    console.info('resource_response_ignored', {
      resource,
      requestId,
      currentRequestId,
    });
  }
}
