import { describe, expect, it } from 'vitest';

import blockSource from '@/features/strategy/DecisionOutcomeBlock.tsx?raw';
import viewModelSource from '@/features/strategy/decisionOutcomeViewModel.ts?raw';
import strategyBlockSource from '@/features/strategy/StrategyExplanationBlock.tsx?raw';
import apiSource from '@/api/strategy.ts?raw';

describe('DecisionOutcomeBlock source contract', () => {
  it('renders the retrospective heading and safe aggregate fields', () => {
    expect(viewModelSource).toContain('Как сработали решения прошлой недели');
    expect(viewModelSource).toContain('status_label');
    expect(blockSource).not.toContain('evidence_count');
    expect(blockSource).not.toContain('result');
  });

  it('does not reference internal identifiers', () => {
    for (const internal of [
      'memory_id',
      'behavior_id',
      'recipe_id',
      'ingredient_id',
      'event_key',
    ]) {
      expect(blockSource).not.toContain(internal);
    }
  });

  it('uses accessible list semantics and visible labels', () => {
    expect(blockSource).toContain('aria-labelledby');
    expect(blockSource).toContain('<ul');
    expect(blockSource).toContain('<li');
    expect(blockSource).toContain('item.label');
  });

  it('is integrated into the existing WeekPage strategy details flow', () => {
    expect(strategyBlockSource).toContain('DecisionOutcomeBlock');
    expect(strategyBlockSource).toContain('decision_outcomes');
  });

  it('normalizes API outcomes instead of trusting raw payloads', () => {
    expect(apiSource).toContain('normalizeDecisionOutcomes');
  });
});
