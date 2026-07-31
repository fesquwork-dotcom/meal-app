import { describe, expect, it } from 'vitest';

import { buildInsightsViewModel } from '@/features/insights/insightsViewModel';
import type { Insight, InsightSummary } from '@/types/insights';

function insight(overrides: Partial<Insight> = {}): Insight {
  return {
    id: 'replacement_health',
    title: 'Замены стали реже',
    summary: 'Замен стало меньше.',
    category: 'progress',
    confidence: { level: 'high', basis: 'trend' },
    status: 'confirmed',
    evidence: {
      sources: ['trend.replacement_rate', 'trend.decision_health'],
      evidence_weeks: 8,
      completed_strategies: 8,
      positive_events: 42,
      replacement_events: 6,
      decision_outcomes: 12,
      coverage: {
        status: 'complete',
        available_since: '2026-05-18',
        oldest_plan_date: '2026-05-18',
        newest_plan_date: '2026-07-13',
      },
      limitations: [],
      unavailable_reasons: [],
    },
    available_since: 'sprint_7_1',
    transparency: {
      title: 'Почему мы так считаем',
      proof_text: 'Основано на последних 8 завершённых планах.',
      coverage_text: 'Данных достаточно для устойчивого вывода.',
      availability_text: null,
      limitations_text: [],
    },
    ...overrides,
  };
}

function summary(insights: Insight[]): InsightSummary {
  return {
    version: 1,
    generated_at: '2026-07-15T12:00:00+00:00',
    insights,
  };
}

describe('buildInsightsViewModel', () => {
  it('shows confirmed insights with friendly evidence labels', () => {
    const result = buildInsightsViewModel(summary([insight()]));
    expect(result?.cards).toHaveLength(1);
    expect(result?.cards[0].confidenceLabel).toBe('Высокая уверенность');
    expect(result?.cards[0].evidenceLabel).toBe(
      'Основано на данных: история замен, итоги решений',
    );
  });

  it('hides informational and insufficient insights', () => {
    const result = buildInsightsViewModel(
      summary([
        insight({ status: 'insufficient_data' }),
        insight({ id: 'replacement_cost', status: 'informational' }),
        insight({ id: 'positive_completion', status: 'confirmed' }),
      ]),
    );
    expect(result?.cards).toHaveLength(1);
    expect(result?.cards[0].id).toBe('positive_completion');
  });

  it('does not expose technical evidence codes in labels', () => {
    const result = buildInsightsViewModel(summary([insight()]));
    const label = result?.cards[0].evidenceLabel ?? '';
    expect(label).not.toContain('trend.');
    expect(label).not.toContain('outcome.');
    expect(label).not.toContain('delta.');
  });

  it('returns null without a summary and an empty model for no insights', () => {
    expect(buildInsightsViewModel(null)).toBeNull();
    expect(buildInsightsViewModel(summary([]))?.cards).toEqual([]);
  });

  it('attaches a transparency view model when the backend provides one', () => {
    const withTransparency = buildInsightsViewModel(summary([insight()]));
    expect(withTransparency?.cards[0].transparency?.toggleLabel).toBe(
      'Почему мы так считаем',
    );

    const withoutTransparency = buildInsightsViewModel(
      summary([insight({ transparency: null })]),
    );
    expect(withoutTransparency?.cards[0].transparency).toBeNull();
  });
});

