import { describe, expect, it } from 'vitest';

import {
  normalizeDecisionExplanationChanges,
  normalizeDecisionExplanations,
} from '@/features/strategy/normalizeDecisionExplanations';

const validItem = {
  version: 1,
  decision_key: 'cooking.cook_days',
  title: 'Дни готовки',
  outcome: 'Дни 1, 3 и 5',
  explanation: 'Основную готовку можно распределить по этим дням.',
  source_label: 'Правила планирования',
  supporting_points: ['Первый', 'Второй'],
  alternative_note: null,
  confidence_label: 'Рассчитано по правилам плана',
};

describe('normalizeDecisionExplanations', () => {
  it('normalizes a trace collection', () => {
    const result = normalizeDecisionExplanations({
      version: 1,
      source: 'trace',
      headline: 'Почему настройки такие',
      summary: 'Безопасное объяснение.',
      explanations: [validItem],
    });
    expect(result?.explanations).toHaveLength(1);
    expect(result?.explanations[0]?.decision_key).toBe('cooking.cook_days');
  });

  it('filters unknown keys and empty strings', () => {
    const result = normalizeDecisionExplanations({
      source: 'trace',
      headline: 'Заголовок',
      summary: 'Описание',
      explanations: [
        validItem,
        { ...validItem, decision_key: 'technical.secret' },
        { ...validItem, title: '   ' },
      ],
    });
    expect(result?.explanations).toHaveLength(1);
  });

  it('filters technical codes embedded in public text', () => {
    const result = normalizeDecisionExplanations({
      source: 'trace',
      headline: 'Заголовок',
      summary: 'Описание',
      explanations: [
        validItem,
        { ...validItem, explanation: 'Сработало COOK_DAYS_BATCH_GOAL' },
      ],
    });
    expect(result?.explanations).toHaveLength(1);
  });

  it('limits explanations and supporting points', () => {
    const result = normalizeDecisionExplanations({
      source: 'trace',
      headline: 'Заголовок',
      summary: 'Описание',
      explanations: Array.from({ length: 12 }, (_, index) => ({
        ...validItem,
        decision_key: index % 2 ? 'shopping.days' : 'cooking.cook_days',
        supporting_points: ['1', '2', '3', '4', '5'],
      })),
    });
    expect(result?.explanations).toHaveLength(8);
    expect(result?.explanations[0]?.supporting_points).toHaveLength(4);
  });

  it('drops unknown confidence labels', () => {
    const result = normalizeDecisionExplanations({
      source: 'trace',
      headline: 'Заголовок',
      summary: 'Описание',
      explanations: [{ ...validItem, confidence_label: '80%' }],
    });
    expect(result?.explanations[0]?.confidence_label).toBeNull();
  });

  it('accepts legacy keys only for legacy source', () => {
    const legacy = { ...validItem, decision_key: 'legacy.0' };
    expect(
      normalizeDecisionExplanations({
        source: 'legacy',
        headline: 'Заголовок',
        summary: 'Описание',
        explanations: [legacy],
      })?.explanations,
    ).toHaveLength(1);
    expect(
      normalizeDecisionExplanations({
        source: 'trace',
        headline: 'Заголовок',
        summary: 'Описание',
        explanations: [legacy],
      })?.explanations,
    ).toHaveLength(0);
  });

  it('normalizes compare changes and rejects malformed values', () => {
    const result = normalizeDecisionExplanationChanges([
      {
        decision_key: 'budget.weekly',
        title: 'Бюджет',
        before: '3 000 ₽',
        after: '4 000 ₽',
        explanation: 'Бюджет изменился.',
        change_type: 'value_changed',
      },
      { decision_key: 'private.key' },
    ]);
    expect(result).toHaveLength(1);
    expect(normalizeDecisionExplanationChanges({})).toBeNull();
  });
});
