import { describe, expect, it } from 'vitest';

import { buildDecisionOutcomeViewModel } from '@/features/strategy/decisionOutcomeViewModel';
import type { DecisionOutcomeSummary } from '@/types/decisionOutcome';

function summary(status: DecisionOutcomeSummary['explanations'][number]['status']) {
  return {
    version: 1,
    evaluated_count: 1,
    successful_count: status === 'successful' ? 1 : 0,
    neutral_count: status === 'neutral' ? 1 : 0,
    unsuccessful_count: status === 'unsuccessful' ? 1 : 0,
    insufficient_data_count: status === 'insufficient_data' ? 1 : 0,
    pending_count: status === 'pending' ? 1 : 0,
    explanations: [
      {
        decision_key: 'cooking.prefer_faster',
        title: 'Быстрые блюда',
        status,
        status_label: 'Статус',
        explanation: 'Описание',
      },
    ],
  } satisfies DecisionOutcomeSummary;
}

describe('buildDecisionOutcomeViewModel', () => {
  it.each([
    ['successful', '✓'],
    ['neutral', '•'],
    ['unsuccessful', '⚠'],
    ['insufficient_data', '•'],
    ['pending', '…'],
  ] as const)('maps %s to a visible text icon', (status, icon) => {
    const result = buildDecisionOutcomeViewModel(summary(status));
    expect(result?.items[0]?.icon).toBe(icon);
    expect(result?.items[0]?.status).toBe(status);
  });

  it('returns null for legacy and empty data', () => {
    expect(buildDecisionOutcomeViewModel(null)).toBeNull();
    expect(
      buildDecisionOutcomeViewModel({ ...summary('successful'), explanations: [] }),
    ).toBeNull();
  });
});
