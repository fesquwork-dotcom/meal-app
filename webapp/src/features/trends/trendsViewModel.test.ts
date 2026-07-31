import { describe, expect, it } from 'vitest';

import { buildTrendsViewModel } from '@/features/trends/trendsViewModel';
import type { TrendMetric, TrendSummary } from '@/types/trends';

const metric = (overrides: Partial<TrendMetric> = {}): TrendMetric => ({
  id: 'replacement_rate',
  title: 'Замены блюд',
  status: 'improving',
  value: null,
  change: null,
  evidence_weeks: 4,
  confidence: { status: 'emerging', weeks: 4, completed_strategies: 4 },
  source: 'история замен',
  available_since: 'phase_1',
  summary_text: 'Есть первые признаки улучшения.',
  capability_note: null,
  ...overrides,
});

const summary = (metrics: TrendMetric[]): TrendSummary => ({
  version: 1,
  generated_at: '2026-07-14T00:00:00+00:00',
  confidence: { status: 'emerging', weeks: 4, completed_strategies: 4 },
  metrics,
});

describe('buildTrendsViewModel', () => {
  it('returns null without a summary', () => {
    expect(buildTrendsViewModel(null)).toBeNull();
    expect(buildTrendsViewModel(undefined)).toBeNull();
  });

  it('maps metrics with russian status and confidence labels', () => {
    const viewModel = buildTrendsViewModel(summary([metric()]));
    expect(viewModel?.title).toBe('Мой прогресс');
    expect(viewModel?.overallLabel).toBe('Первые наблюдения');
    expect(viewModel?.metrics[0].statusLabel).toBe('Улучшается');
    expect(viewModel?.metrics[0].confidenceLabel).toBe('Первые наблюдения');
    expect(viewModel?.metrics[0].summaryText).toBe(
      'Есть первые признаки улучшения.',
    );
  });

  it('shows change only for established metrics', () => {
    const emerging = buildTrendsViewModel(
      summary([metric({ change: -18 })]),
    );
    expect(emerging?.metrics[0].changeLabel).toBeNull();

    const established = buildTrendsViewModel(
      summary([
        metric({
          change: -18,
          confidence: { status: 'established', weeks: 8, completed_strategies: 8 },
        }),
        metric({
          id: 'decision_health',
          status: 'worsening',
          change: 27,
          confidence: { status: 'established', weeks: 8, completed_strategies: 8 },
        }),
      ]),
    );
    expect(established?.metrics[0].changeLabel).toBe('-18%');
    expect(established?.metrics[1].changeLabel).toBe('+27%');
  });

  it('pluralizes evidence weeks correctly', () => {
    const viewModel = buildTrendsViewModel(
      summary([
        metric({ evidence_weeks: 1 }),
        metric({ id: 'decision_health', evidence_weeks: 3 }),
        metric({ id: 'preference_stability', evidence_weeks: 7 }),
        metric({ id: 'positive_completion', evidence_weeks: 0 }),
      ]),
    );
    expect(viewModel?.metrics[0].evidenceLabel).toBe('1 неделя наблюдений');
    expect(viewModel?.metrics[1].evidenceLabel).toBe('3 недели наблюдений');
    expect(viewModel?.metrics[2].evidenceLabel).toBe('7 недель наблюдений');
    expect(viewModel?.metrics[3].evidenceLabel).toBe('нет завершённых недель');
  });

  it('passes the capability note through untouched', () => {
    const note =
      'Эта метрика рассчитывается только для планов, созданных после обновления приложения.';
    const viewModel = buildTrendsViewModel(
      summary([metric({ capability_note: note })]),
    );
    expect(viewModel?.metrics[0].capabilityNote).toBe(note);
  });

  it('never exposes raw internal fields', () => {
    const viewModel = buildTrendsViewModel(summary([metric()]));
    const serialized = JSON.stringify(viewModel);
    expect(serialized).not.toContain('available_since');
    expect(serialized).not.toContain('generated_at');
    expect(serialized).not.toContain('completed_strategies');
  });
});
