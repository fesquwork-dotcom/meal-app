import { describe, expect, it } from 'vitest';

import { buildDecisionExplanationViewModel } from '@/features/strategy/decisionExplanationViewModel';
import type { DecisionExplanationCollection } from '@/types/decisionExplanation';

const collection: DecisionExplanationCollection = {
  version: 1,
  source: 'trace',
  headline: 'Почему выбраны настройки',
  summary: 'Краткое описание',
  explanations: Array.from({ length: 6 }, (_, index) => ({
    version: 1,
    decision_key: `cooking.${index}`,
    title: `Решение ${index}`,
    outcome: `Значение ${index}`,
    explanation: `Описание ${index}`,
    source_label: 'Правила планирования',
    supporting_points: [],
    alternative_note: null,
    confidence_label: 'Рассчитано по правилам плана',
  })),
};

describe('buildDecisionExplanationViewModel', () => {
  it('shows four entries by default', () => {
    const result = buildDecisionExplanationViewModel(collection);
    expect(result?.visible).toHaveLength(4);
    expect(result?.hiddenCount).toBe(2);
  });

  it('shows all entries on request', () => {
    const result = buildDecisionExplanationViewModel(collection, true);
    expect(result?.visible).toHaveLength(6);
    expect(result?.hiddenCount).toBe(0);
  });

  it('keeps legacy source', () => {
    const result = buildDecisionExplanationViewModel({ ...collection, source: 'legacy' });
    expect(result?.source).toBe('legacy');
  });

  it('returns null for missing and empty collections', () => {
    expect(buildDecisionExplanationViewModel(null)).toBeNull();
    expect(
      buildDecisionExplanationViewModel({ ...collection, explanations: [] }),
    ).toBeNull();
  });
});
