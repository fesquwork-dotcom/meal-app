import { describe, expect, it } from 'vitest';

import blockSource from '@/features/strategy/DecisionExplanationBlock.tsx?raw';
import weekPageSource from '@/pages/WeekPage.tsx?raw';
import strategyBlockSource from '@/features/strategy/StrategyExplanationBlock.tsx?raw';
import previewSource from '@/features/menu-generator/GenerateMenuSheet.tsx?raw';

describe('DecisionExplanationBlock source contract', () => {
  it('uses accessible disclosure controls', () => {
    expect(blockSource).toContain('aria-expanded');
    expect(blockSource).toContain('aria-controls');
    expect(blockSource).toContain('role="region"');
    expect(blockSource).toContain('aria-labelledby');
  });

  it('shows source as text, not color alone', () => {
    expect(blockSource).toContain('Источник:');
    expect(blockSource).toContain('confidence_label');
  });

  it('supports collapsed and show-more behavior', () => {
    expect(blockSource).toContain('showAll');
    expect(blockSource).toContain('Показать остальные');
    expect(blockSource).toContain('expanded');
  });

  it('is integrated with the existing WeekPage explanation block', () => {
    expect(weekPageSource).toContain('StrategyExplanationBlock');
    expect(strategyBlockSource).toContain('DecisionExplanationBlock');
    expect(strategyBlockSource).toContain('decision_explanations');
  });

  it('renders compact preview explanations without raw trace', () => {
    expect(blockSource).toContain('Главные правила будущего плана');
    expect(previewSource).toContain('compact');
    expect(previewSource).toContain('decision_explanations');
    expect(previewSource).not.toContain('decision_trace');
  });
});
