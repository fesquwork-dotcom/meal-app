import { describe, expect, it } from 'vitest';

import { normalizeLearnedPreferenceEffectiveness } from '@/features/learned-preferences/normalizeLearnedPreferenceEffectiveness';

const valid = {
  status: 'emerging',
  confidence: 'partial',
  evidence_plans: 3,
  generation: 0,
  title: 'Есть первые положительные признаки',
  summary: 'Есть первые признаки, что это предпочтение подходит вам.',
  evidence_text:
    'Основано на 3 завершённых планах, где предпочтение действительно применялось.',
  limitations: ['Выборка пока небольшая — вывод предварительный.'],
};

describe('normalizeLearnedPreferenceEffectiveness', () => {
  it('returns null for nullish or non-object values', () => {
    expect(normalizeLearnedPreferenceEffectiveness(null)).toBeNull();
    expect(normalizeLearnedPreferenceEffectiveness(undefined)).toBeNull();
    expect(normalizeLearnedPreferenceEffectiveness('x')).toBeNull();
  });

  it('keeps a valid insufficient payload', () => {
    const result = normalizeLearnedPreferenceEffectiveness({
      ...valid,
      status: 'insufficient_data',
      confidence: 'insufficient',
      evidence_plans: 1,
      title: 'Пока собираем данные',
    });
    expect(result?.status).toBe('insufficient_data');
    expect(result?.evidence_plans).toBe(1);
  });

  it('keeps emerging, effective, neutral, and ineffective statuses', () => {
    for (const status of [
      'emerging',
      'effective',
      'neutral',
      'ineffective',
    ] as const) {
      expect(
        normalizeLearnedPreferenceEffectiveness({ ...valid, status })?.status,
      ).toBe(status);
    }
  });

  it('rejects unknown status or confidence', () => {
    expect(
      normalizeLearnedPreferenceEffectiveness({ ...valid, status: 'great' }),
    ).toBeNull();
    expect(
      normalizeLearnedPreferenceEffectiveness({
        ...valid,
        confidence: 'high',
      }),
    ).toBeNull();
  });

  it('rejects out-of-range evidence_plans and internal counters', () => {
    expect(
      normalizeLearnedPreferenceEffectiveness({
        ...valid,
        evidence_plans: 13,
      }),
    ).toBeNull();
    expect(
      normalizeLearnedPreferenceEffectiveness({
        ...valid,
        generation: 4,
      }),
    ).toBeNull();
    expect(
      normalizeLearnedPreferenceEffectiveness({
        ...valid,
        positive_evidence_count: 2,
      }),
    ).toBeNull();
  });

  it('rejects texts that leak internal identifiers', () => {
    expect(
      normalizeLearnedPreferenceEffectiveness({
        ...valid,
        summary: 'strategy_id = leak',
      }),
    ).toBeNull();
  });
});
