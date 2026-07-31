import type { AsyncResourceState } from '@/features/async-resource/types';
import type { StrategyWorkflowError } from '@/features/strategy-workflow/types';

export function hasResourceData<T>(state: AsyncResourceState<T>): state is AsyncResourceState<T> & {
  data: T;
} {
  return state.data !== null;
}

export function isInitialLoading<T>(state: AsyncResourceState<T>): boolean {
  return state.status === 'loading' || state.status === 'idle';
}

export function isRefreshing<T>(state: AsyncResourceState<T>): boolean {
  return state.status === 'refreshing';
}

export function isInitialLoadError<T>(state: AsyncResourceState<T>): boolean {
  return state.status === 'error' && state.data === null;
}

export function isRefreshError<T>(state: AsyncResourceState<T>): boolean {
  return state.status === 'error' && state.data !== null;
}

export function canRetryResource<T>(state: AsyncResourceState<T>): boolean {
  return state.status === 'error';
}

export function resourceError<T>(state: AsyncResourceState<T>): StrategyWorkflowError | null {
  return state.status === 'error' ? state.error : null;
}
