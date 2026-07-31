import { describe, expect, it } from 'vitest';

import memoryHookSource from '@/hooks/useMemorySignals.ts?raw';
import behaviorHookSource from '@/hooks/useBehaviorInsights.ts?raw';
import behaviorStateSource from '@/features/behavior/behaviorInsightsState.ts?raw';
import profileProviderSource from '@/features/profile/ProfileProvider.tsx?raw';
import policiesSource from '@/features/async-resource/resourceFreshnessPolicy.ts?raw';

describe('freshnessCleanup', () => {
  it('policies are centralized', () => {
    expect(policiesSource).toContain('RESOURCE_FRESHNESS_POLICIES');
    expect(policiesSource).toContain('staleAfterMs');
    expect(memoryHookSource).toContain('RESOURCE_FRESHNESS_POLICIES.memory');
    expect(behaviorHookSource).toContain('RESOURCE_FRESHNESS_POLICIES.behavior');
    expect(profileProviderSource).toContain('RESOURCE_FRESHNESS_POLICIES.profile');
  });

  it('Memory/Behavior use per-card action error maps', () => {
    expect(memoryHookSource).toContain('actionErrorsBySignalId');
    expect(behaviorStateSource).toContain('actionErrorsByInsightId');
    expect(behaviorHookSource).toContain('actionErrorsByInsightId');
  });

  it('hooks use AbortSignal and abort detection', () => {
    expect(memoryHookSource).toContain('isRequestAbortError');
    expect(memoryHookSource).toContain('signal');
    expect(behaviorHookSource).toContain('isRequestAbortError');
    expect(profileProviderSource).toContain('createResourceRequestController');
    expect(profileProviderSource).toContain('isRequestAbortError');
  });
});
