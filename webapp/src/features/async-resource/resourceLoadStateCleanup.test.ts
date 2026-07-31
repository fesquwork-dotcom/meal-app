import { describe, expect, it } from 'vitest';

import profileProviderSource from '@/features/profile/ProfileProvider.tsx?raw';
import memoryHookSource from '@/hooks/useMemorySignals.ts?raw';
import behaviorHookSource from '@/hooks/useBehaviorInsights.ts?raw';
import behaviorStateSource from '@/features/behavior/behaviorInsightsState.ts?raw';
import currentStrategySource from '@/hooks/useCurrentStrategy.ts?raw';
import strategyByIdSource from '@/hooks/useStrategyById.ts?raw';

describe('resourceLoadStateCleanup', () => {
  it('ProfileProvider load path uses AsyncResourceState not string error', () => {
    expect(profileProviderSource).toContain('AsyncResourceState<ProfileServerState>');
    expect(profileProviderSource).toContain('error: StrategyWorkflowError | null');
    expect(profileProviderSource).not.toMatch(/error:\s*string\s*\|\s*null/);
    expect(profileProviderSource).not.toContain('.message);\n      setIsProfileLoaded(false)');
  });

  it('useMemorySignals uses typed resource error', () => {
    expect(memoryHookSource).toContain('AsyncResourceState');
    expect(memoryHookSource).toContain('classifyStrategyWorkflowError');
    expect(memoryHookSource).not.toMatch(/useState<unknown>\(null\)/);
    expect(memoryHookSource).not.toContain('setSignals([])');
  });

  it('useBehaviorInsights / reducer remove string loadError', () => {
    expect(behaviorStateSource).not.toMatch(/loadError:\s*string/);
    expect(behaviorHookSource).toContain('resourceError');
    expect(behaviorHookSource).not.toContain("message: classifyStrategyWorkflowError(err).message");
  });

  it('strategy hooks use StrategyWorkflowError resource state', () => {
    expect(currentStrategySource).toContain('AsyncResourceState');
    expect(currentStrategySource).toContain('classifyStrategyWorkflowError');
    expect(currentStrategySource).not.toMatch(/useState<unknown>\(null\)/);
    expect(strategyByIdSource).toContain('AsyncResourceState');
    expect(strategyByIdSource).not.toMatch(/setData\(null\)/);
  });
});
