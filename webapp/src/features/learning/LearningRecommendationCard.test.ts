import { describe, expect, it } from 'vitest';

import sectionSource from '@/features/learning/LearningRecommendationsSection.tsx?raw';
import profilePageSource from '@/pages/ProfilePage.tsx?raw';
import weekPageSource from '@/pages/WeekPage.tsx?raw';

describe('Learning recommendation card accessibility and placement', () => {
  it('renders the ProfilePage section and never appears on WeekPage', () => {
    expect(profilePageSource).toContain('LearningRecommendationsSection');
    expect(sectionSource).toContain('Что можно улучшить');
    expect(weekPageSource).not.toContain('LearningRecommendationsSection');
    expect(weekPageSource).not.toContain('Что можно улучшить');
  });

  it('provides accessible expansion, dialog, keyboard close, and focus restore', () => {
    expect(sectionSource).toContain('aria-expanded');
    expect(sectionSource).toContain('<Modal');
    expect(sectionSource).toContain('triggerRef.current?.focus()');
    expect(sectionSource).toContain('titleId="learning-recommendation-title"');
  });

  it('explains reason, effect, reversibility, and unchanged behavior', () => {
    expect(sectionSource).toContain('Почему появилась рекомендация');
    expect(sectionSource).toContain('Что изменится');
    expect(sectionSource).toContain('Что не изменится и как отменить');
    expect(sectionSource).toContain('только на следующий план');
  });

  it('does not render internal trace or evidence fields', () => {
    for (const forbidden of [
      'event_key',
      'meal_id',
      'recipe_id',
      'ingredient_id',
      'trace_json',
      'evidence_json',
      'source_strategy_id',
    ]) {
      expect(sectionSource).not.toContain(forbidden);
    }
  });
});
