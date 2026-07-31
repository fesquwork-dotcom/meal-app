import { describe, expect, it } from 'vitest';

import apiSource from '@/api/learning.ts?raw';
import sectionSource from '@/features/learning/LearningRecommendationsSection.tsx?raw';
import profileApiSource from '@/api/profile.ts?raw';
import profileServerUpdateSource from '@/features/profile/profileServerUpdate.ts?raw';
import invalidationSource from '@/features/strategy-inputs/strategyInputInvalidation.ts?raw';

describe('Learning human-in-the-loop workflow', () => {
  it('uses separate list, accept, and dismiss endpoints', () => {
    expect(apiSource).toContain('/api/learning/recommendations');
    expect(apiSource).toContain('/accept');
    expect(apiSource).toContain('/dismiss');
    expect(apiSource).not.toContain('/api/profile');
  });

  it('accepts first and then uses the existing CAS Profile PUT', () => {
    const acceptIndex = sectionSource.indexOf('acceptLearningRecommendation(');
    const saveIndex = sectionSource.indexOf('saveProfile(');
    expect(acceptIndex).toBeGreaterThan(-1);
    expect(saveIndex).toBeGreaterThan(acceptIndex);
    expect(sectionSource).toContain('serverRevision');
    expect(profileApiSource).toContain("api.put<GetProfileResponse>");
    expect(profileApiSource).toContain('expectedRevision');
  });

  it('coordinates the saved profile as one strategy-input change', () => {
    expect(sectionSource).toContain("source: 'learning_recommendation'");
    expect(sectionSource).toContain(
      "notifyStrategyInputsChanged('learning_recommendation_applied')",
    );
    expect(profileServerUpdateSource).toContain("'learning_recommendation'");
    expect(invalidationSource).toContain("'learning_recommendation_applied'");
  });

  it('blocks application while a local profile draft exists', () => {
    expect(sectionSource).toContain('hasProfileDraft');
    expect(sectionSource).toContain('Сначала сохраните изменения профиля.');
  });

  it('never automatically applies a recommendation during loading', () => {
    const loadEffect = sectionSource.slice(
      sectionSource.indexOf('useEffect(() =>'),
      sectionSource.indexOf('const closeDetails'),
    );
    expect(loadEffect).toContain('getLearningRecommendations');
    expect(loadEffect).not.toContain('saveProfile');
    expect(loadEffect).not.toContain('acceptLearningRecommendation');
  });
});
