import { describe, expect, it } from 'vitest';

import { buildInsightTransparencyViewModel } from '@/features/insights/insightTransparencyViewModel';
import type { Insight } from '@/types/insights';

function insight(overrides: Partial<Insight> = {}): Insight {
  return {
    id: 'replacement_health',
    title: 'Замены стали реже',
    summary: 'Замен стало меньше.',
    category: 'progress',
    confidence: { level: 'high', basis: 'trend' },
    status: 'confirmed',
    evidence: {
      sources: ['trend.replacement_rate'],
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

describe('buildInsightTransparencyViewModel', () => {
  it('returns null when the backend sent no transparency', () => {
    expect(buildInsightTransparencyViewModel(insight({ transparency: null }))).toBeNull();
  });

  it('builds proof, coverage, positive events, and freshest-data lines', () => {
    const result = buildInsightTransparencyViewModel(insight());
    expect(result?.toggleLabel).toBe('Почему мы так считаем');
    expect(result?.lines.map((line) => line.id)).toEqual([
      'proof',
      'coverage',
      'positive-events',
      'newest-data',
    ]);
    expect(result?.lines[0]).toMatchObject({
      tone: 'ok',
      text: 'Основано на последних 8 завершённых планах.',
    });
    expect(result?.lines[3].text).toBe('Последние данные — 13 июля 2026');
  });

  it('marks partial coverage and limitations as warnings', () => {
    const base = insight();
    const result = buildInsightTransparencyViewModel(
      insight({
        evidence: {
          ...base.evidence,
          positive_events: 0,
          coverage: { ...base.evidence.coverage!, status: 'partial' },
        },
        transparency: {
          ...base.transparency!,
          coverage_text: 'Данных пока хватает только для предварительного вывода.',
          limitations_text: ['Некоторые старые планы не содержат необходимых данных.'],
        },
      }),
    );
    const coverageLine = result?.lines.find((line) => line.id === 'coverage');
    expect(coverageLine?.tone).toBe('warning');
    const limitationLine = result?.lines.find((line) => line.id === 'limitation-0');
    expect(limitationLine).toMatchObject({
      tone: 'warning',
      text: 'Некоторые старые планы не содержат необходимых данных.',
    });
    expect(result?.lines.some((line) => line.id === 'positive-events')).toBe(false);
  });

  it('keeps insufficient coverage neutral without dates', () => {
    const base = insight();
    const result = buildInsightTransparencyViewModel(
      insight({
        evidence: {
          ...base.evidence,
          positive_events: 0,
          coverage: {
            status: 'insufficient',
            available_since: null,
            oldest_plan_date: null,
            newest_plan_date: null,
          },
        },
        transparency: {
          ...base.transparency!,
          proof_text: 'Пока собираем данные.',
          coverage_text: 'Для надёжного вывода нужно больше завершённых планов.',
        },
      }),
    );
    expect(result?.lines.map((line) => line.id)).toEqual(['proof', 'coverage']);
    expect(result?.lines.every((line) => line.tone === 'neutral')).toBe(true);
  });

  it('adds an availability warning when data starts later than history', () => {
    const base = insight();
    const result = buildInsightTransparencyViewModel(
      insight({
        transparency: {
          ...base.transparency!,
          availability_text: 'Есть данные только после обновления приложения.',
        },
      }),
    );
    const availability = result?.lines.find((line) => line.id === 'availability');
    expect(availability).toMatchObject({
      tone: 'warning',
      text: 'Есть данные только после обновления приложения.',
    });
  });
});
