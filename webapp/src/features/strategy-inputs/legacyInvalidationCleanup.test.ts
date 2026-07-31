import { describe, expect, it } from 'vitest';

import profileProviderSource from '@/features/profile/ProfileProvider.tsx?raw';
import generateSheetSource from '@/features/menu-generator/GenerateMenuSheet.tsx?raw';
import previewReducerSource from '@/features/menu-generator/generationPreviewReducer.ts?raw';
import compareSource from '@/features/strategy/StrategyCompareSection.tsx?raw';
import strategyInputsIndex from '@/features/strategy-inputs/index.ts?raw';

describe('legacy invalidation cleanup', () => {
  const productionSources = [
    profileProviderSource,
    generateSheetSource,
    previewReducerSource,
    compareSource,
    strategyInputsIndex,
  ];

  it('does not expose notifyProfileExternallyUpdated in production sources', () => {
    for (const source of productionSources) {
      expect(source).not.toContain('notifyProfileExternallyUpdated');
    }
  });

  it('does not expose previewStaleNonce in production sources', () => {
    for (const source of productionSources) {
      expect(source).not.toContain('previewStaleNonce');
    }
  });

  it('does not dispatch legacy stale action', () => {
    expect(previewReducerSource).not.toContain("type: 'stale'");
    expect(previewReducerSource).not.toContain('type: "stale"');
    expect(previewReducerSource).not.toMatch(/case 'stale'/);
    expect(generateSheetSource).not.toContain("type: 'stale'");
  });
});
