import { describe, expect, it } from 'vitest';

import profileProviderSource from '@/features/profile/ProfileProvider.tsx?raw';
import behaviorHookSource from '@/hooks/useBehaviorInsights.ts?raw';
import memoryHookSource from '@/hooks/useMemorySignals.ts?raw';
import profilePageSource from '@/pages/ProfilePage.tsx?raw';
import generateSheetSource from '@/features/menu-generator/GenerateMenuSheet.tsx?raw';
import memorySectionSource from '@/features/memory/MemorySignalsSection.tsx?raw';
import behaviorSectionSource from '@/features/behavior/BehaviorInsightsSection.tsx?raw';

describe('workflowBooleanCleanup', () => {
  it('ProfileProvider saveProfileDraft returns WorkflowResult alias not boolean', () => {
    expect(profileProviderSource).not.toMatch(/saveProfileDraft:\s*\(\)\s*=>\s*Promise<boolean>/);
    expect(profileProviderSource).toMatch(/saveProfileDraft:\s*\(\)\s*=>\s*Promise<SaveProfileResult>/);
    expect(profileProviderSource).toContain('Promise<SaveProfileResult>');
  });

  it('Behavior hook mutating actions return WorkflowResult aliases', () => {
    expect(behaviorHookSource).not.toMatch(/:\s*Promise<boolean>/);
    expect(behaviorHookSource).toContain('Promise<BehaviorInsightActionResult>');
    expect(behaviorHookSource).toContain('Promise<BehaviorRecommendationResult>');
  });

  it('Memory hook mutating actions return WorkflowResult aliases', () => {
    expect(memoryHookSource).not.toMatch(/:\s*Promise<boolean>/);
    expect(memoryHookSource).toContain('Promise<MemorySignalActionResult>');
    expect(memoryHookSource).toContain('Promise<MemoryPromotionResult>');
  });

  it('production sections branch on typed .ok results and avoid parseApiError', () => {
    expect(profilePageSource).toContain('saved.ok');
    expect(generateSheetSource).toContain('!saved.ok');
    expect(memorySectionSource).toContain('result.ok');
    expect(behaviorSectionSource).toContain('result.ok');
    expect(behaviorSectionSource).not.toContain('parseApiError');
    expect(memorySectionSource).not.toContain('parseApiError');
  });
});
