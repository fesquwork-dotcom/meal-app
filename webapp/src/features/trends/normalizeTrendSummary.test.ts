import { describe, expect, it } from 'vitest';

import { normalizeTrendSummary } from '@/features/trends/normalizeTrendSummary';

const confidence = (status: string, weeks = 4) => ({
  status,
  weeks,
  completed_strategies: weeks,
});

const metric = (overrides: Record<string, unknown> = {}) => ({
  id: 'replacement_rate',
  title: 'Замены блюд',
  status: 'improving',
  value: null,
  change: null,
  evidence_weeks: 4,
  confidence: confidence('emerging'),
  source: 'история замен',
  available_since: 'phase_1',
  summary_text: 'Есть первые признаки улучшения.',
  capability_note: null,
  ...overrides,
});

const summary = (overrides: Record<string, unknown> = {}) => ({
  version: 1,
  generated_at: '2026-07-14T00:00:00+00:00',
  confidence: confidence('emerging'),
  metrics: [metric()],
  ...overrides,
});

describe('normalizeTrendSummary', () => {
  it('accepts a valid payload', () => {
    const result = normalizeTrendSummary(summary());
    expect(result).not.toBeNull();
    expect(result?.metrics).toHaveLength(1);
    expect(result?.metrics[0].id).toBe('replacement_rate');
  });

  it('rejects non-object payloads', () => {
    expect(normalizeTrendSummary(null)).toBeNull();
    expect(normalizeTrendSummary('text')).toBeNull();
    expect(normalizeTrendSummary([])).toBeNull();
  });

  it('drops metrics with unknown ids, statuses, or availability', () => {
    const result = normalizeTrendSummary(
      summary({
        metrics: [
          metric({ id: 'internal_metric' }),
          metric({ status: 'exploding' }),
          metric({ available_since: 'sprint_9_9' }),
          metric(),
        ],
      }),
    );
    expect(result?.metrics).toHaveLength(1);
  });

  it('enforces the confidence gate on quantitative fields', () => {
    const emerging = normalizeTrendSummary(
      summary({
        metrics: [metric({ value: '12%', change: -18 })],
      }),
    );
    expect(emerging?.metrics[0].value).toBeNull();
    expect(emerging?.metrics[0].change).toBeNull();

    const established = normalizeTrendSummary(
      summary({
        metrics: [
          metric({
            value: '12%',
            change: -18,
            confidence: confidence('established', 8),
          }),
        ],
      }),
    );
    expect(established?.metrics[0].value).toBe('12%');
    expect(established?.metrics[0].change).toBe(-18);
  });

  it('rejects unsafe value formats and out-of-range changes', () => {
    const result = normalizeTrendSummary(
      summary({
        metrics: [
          metric({
            value: 'DROP TABLE',
            change: 5000,
            confidence: confidence('established', 8),
          }),
        ],
      }),
    );
    expect(result?.metrics[0].value).toBeNull();
    expect(result?.metrics[0].change).toBeNull();
  });

  it('drops texts containing technical identifiers', () => {
    const result = normalizeTrendSummary(
      summary({
        metrics: [metric({ summary_text: 'strategy_id abc leaked' })],
      }),
    );
    expect(result?.metrics).toHaveLength(0);
  });

  it('limits metrics to ten entries', () => {
    const result = normalizeTrendSummary(
      summary({ metrics: Array.from({ length: 20 }, () => metric()) }),
    );
    expect(result?.metrics).toHaveLength(10);
  });

  it('requires a valid overall confidence and timestamp', () => {
    expect(normalizeTrendSummary(summary({ confidence: null }))).toBeNull();
    expect(
      normalizeTrendSummary(summary({ confidence: confidence('certain') })),
    ).toBeNull();
    expect(normalizeTrendSummary(summary({ generated_at: 42 }))).toBeNull();
  });
});
