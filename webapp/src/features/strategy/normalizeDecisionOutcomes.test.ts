import { describe, expect, it } from 'vitest';

import { normalizeDecisionOutcomes } from '@/features/strategy/normalizeDecisionOutcomes';

const explanation = {
  decision_key: 'cooking.prefer_faster',
  title: 'Быстрые блюда',
  status: 'successful',
  status_label: 'Решение сработало хорошо',
  explanation: 'Большинство блюд не потребовало замен.',
};

describe('normalizeDecisionOutcomes', () => {
  it('normalizes successful, neutral, unsuccessful and pending items', () => {
    const result = normalizeDecisionOutcomes({
      version: 1,
      evaluated_count: 4,
      successful_count: 1,
      neutral_count: 1,
      unsuccessful_count: 1,
      insufficient_data_count: 0,
      pending_count: 1,
      explanations: [
        explanation,
        { ...explanation, decision_key: 'shopping.days', status: 'neutral' },
        { ...explanation, decision_key: 'cooking.cook_days', status: 'unsuccessful' },
        { ...explanation, decision_key: 'planning.prefer_familiar_meals', status: 'pending' },
      ],
    });
    expect(result?.explanations).toHaveLength(4);
    expect(result?.unsuccessful_count).toBe(1);
  });

  it('returns null for legacy and malformed payloads', () => {
    expect(normalizeDecisionOutcomes(null)).toBeNull();
    expect(normalizeDecisionOutcomes('broken')).toBeNull();
  });

  it('filters unknown keys and statuses', () => {
    const result = normalizeDecisionOutcomes({
      explanations: [
        explanation,
        { ...explanation, decision_key: 'budget.weekly' },
        { ...explanation, status: 'probability_80' },
      ],
    });
    expect(result?.explanations).toHaveLength(1);
  });

  it('filters internal identifiers and technical codes', () => {
    const result = normalizeDecisionOutcomes({
      explanations: [
        explanation,
        { ...explanation, explanation: 'recipe_id=private' },
        { ...explanation, explanation: 'OUTCOME_INTERNAL_RULE' },
      ],
    });
    expect(result?.explanations).toHaveLength(1);
  });

  it('limits explanations and sanitizes invalid counts', () => {
    const result = normalizeDecisionOutcomes({
      evaluated_count: -5,
      explanations: Array.from({ length: 8 }, () => explanation),
    });
    expect(result?.evaluated_count).toBe(0);
    expect(result?.explanations).toHaveLength(5);
  });
});
