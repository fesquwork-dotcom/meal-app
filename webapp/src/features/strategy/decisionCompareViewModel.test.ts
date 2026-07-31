import { describe, expect, it } from 'vitest';

import { buildDecisionCompareViewModel } from '@/features/strategy/decisionCompareViewModel';
import viewModelSource from '@/features/strategy/decisionCompareViewModel.ts?raw';
import compareSource from '@/features/strategy/StrategyCompareSection.tsx?raw';

const change = {
  decision_key: 'cooking.cook_days',
  title: 'Дни готовки',
  before: 'Дни 1, 3 и 5',
  after: 'Каждый день',
  explanation: 'Теперь выбран быстрый режим.',
  change_type: 'value_changed' as const,
};

describe('decision compare view model', () => {
  it('builds changed state', () => {
    const result = buildDecisionCompareViewModel([change]);
    expect(result?.unchanged).toBe(false);
    expect(result?.changes[0]).toEqual(change);
  });

  it('builds no-change message state', () => {
    const result = buildDecisionCompareViewModel([]);
    expect(result?.unchanged).toBe(true);
    expect(result?.changes).toEqual([]);
  });

  it('hides legacy partial comparison', () => {
    expect(buildDecisionCompareViewModel(null)).toBeNull();
    expect(buildDecisionCompareViewModel(undefined)).toBeNull();
  });

  it('limits changes', () => {
    const result = buildDecisionCompareViewModel(Array.from({ length: 12 }, () => change));
    expect(result?.changes).toHaveLength(8);
  });

  it('is rendered after settings diff with safe text', () => {
    expect(viewModelSource).toContain('Почему изменятся правила');
    expect(compareSource).toContain('Причины основных решений не изменились');
    expect(compareSource).not.toContain('rule_code');
    expect(compareSource).not.toContain('reason_code');
  });
});
