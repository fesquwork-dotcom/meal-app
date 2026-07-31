export type ResourceFreshness = 'unknown' | 'fresh' | 'stale';

export type RefreshOnMountPolicy = 'always' | 'if_stale' | 'never';

export interface ResourceFreshnessPolicy {
  staleAfterMs: number;
  refreshOnMount: RefreshOnMountPolicy;
}

export type ResourcePolicyKey =
  | 'profile'
  | 'memory'
  | 'behavior'
  | 'currentStrategy'
  | 'strategyById';

/** Per-resource freshness policies (SPA session; no polling). */
export const RESOURCE_FRESHNESS_POLICIES: Record<ResourcePolicyKey, ResourceFreshnessPolicy> = {
  profile: { staleAfterMs: 5 * 60_000, refreshOnMount: 'if_stale' },
  memory: { staleAfterMs: 2 * 60_000, refreshOnMount: 'if_stale' },
  behavior: { staleAfterMs: 2 * 60_000, refreshOnMount: 'if_stale' },
  currentStrategy: { staleAfterMs: 5 * 60_000, refreshOnMount: 'if_stale' },
  /** Lifecycle status can change; 5 minutes balances immutability vs status freshness. */
  strategyById: { staleAfterMs: 5 * 60_000, refreshOnMount: 'if_stale' },
};
