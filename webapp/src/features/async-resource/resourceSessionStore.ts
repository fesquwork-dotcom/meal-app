import type { AsyncResourceState } from '@/features/async-resource/types';
import { createInitialAsyncResourceState } from '@/features/async-resource/types';

/**
 * In-memory SPA session holder so section remounts can reuse last resource state
 * without localStorage / Query-style global cache.
 */
export function createResourceSessionStore<T>() {
  let snapshot: AsyncResourceState<T> | null = null;

  return {
    read(): AsyncResourceState<T> {
      return snapshot ?? createInitialAsyncResourceState<T>();
    },
    write(state: AsyncResourceState<T>): void {
      snapshot = state;
    },
    clear(): void {
      snapshot = null;
    },
  };
}
