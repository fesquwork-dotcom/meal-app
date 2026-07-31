import type { AsyncResourceState } from '@/features/async-resource/types';
import type {
  ResourceFreshness,
  ResourceFreshnessPolicy,
} from '@/features/async-resource/resourceFreshnessPolicy';
import { hasResourceData } from '@/features/async-resource/asyncResourceSelectors';

/**
 * Pure freshness from lastUpdatedAt. age >= staleAfterMs → stale.
 * Clock is injectable for tests.
 */
export function getResourceFreshness(
  lastUpdatedAt: number | null,
  policy: ResourceFreshnessPolicy,
  now: number,
): ResourceFreshness {
  if (lastUpdatedAt === null) {
    return 'unknown';
  }
  const age = now - lastUpdatedAt;
  if (age < policy.staleAfterMs) {
    return 'fresh';
  }
  return 'stale';
}

export function selectResourceFreshness<T>(
  state: AsyncResourceState<T>,
  policy: ResourceFreshnessPolicy,
  now: number,
): ResourceFreshness {
  return getResourceFreshness(state.lastUpdatedAt, policy, now);
}

/**
 * Whether a mount effect should start a load/refresh.
 * Manual refresh() always loads separately.
 */
export function shouldLoadResourceOnMount<T>(
  state: AsyncResourceState<T>,
  policy: ResourceFreshnessPolicy,
  now: number,
): boolean {
  if (state.status === 'loading' || state.status === 'refreshing') {
    return false;
  }
  if (!hasResourceData(state)) {
    return true;
  }
  if (policy.refreshOnMount === 'never') {
    return false;
  }
  if (policy.refreshOnMount === 'always') {
    return true;
  }
  // if_stale
  return selectResourceFreshness(state, policy, now) !== 'fresh';
}

export function logResourceCacheHit(resource: string, freshness: ResourceFreshness): void {
  if (import.meta.env.DEV) {
    console.info('resource_cache_hit', { resource, freshness });
  }
}

export function logResourceCacheStale(resource: string, freshness: ResourceFreshness): void {
  if (import.meta.env.DEV) {
    console.info('resource_cache_stale', { resource, freshness });
  }
}
