import { describe, expect, it } from 'vitest';

import { normalizeInsightSummary } from '@/features/insights/normalizeInsightSummary';

const validInsight = {
  id: 'replacement_health',
  title: 'Замены стали реже',
  summary: 'Замен стало меньше.',
  category: 'progress',
  confidence: { level: 'high', basis: 'trend' },
  status: 'confirmed',
  evidence: {
    sources: ['trend.replacement_rate', 'trend.decision_health'],
  },
  available_since: 'sprint_7_1',
};

describe('normalizeInsightSummary', () => {
  it('keeps a valid privacy-safe summary', () => {
    const result = normalizeInsightSummary({
      version: 1,
      generated_at: '2026-07-15T12:00:00+00:00',
      insights: [validInsight],
    });
    expect(result?.insights).toHaveLength(1);
    expect(result?.insights[0].id).toBe('replacement_health');
    expect(result?.insights[0].evidence.sources).toEqual([
      'trend.replacement_rate',
      'trend.decision_health',
    ]);
  });

  it('drops unknown ids, categories, confidence, and statuses', () => {
    const result = normalizeInsightSummary({
      version: 1,
      generated_at: '2026-07-15T12:00:00+00:00',
      insights: [
        { ...validInsight, id: 'secret' },
        { ...validInsight, category: 'health' },
        { ...validInsight, status: 'guessed' },
        { ...validInsight, confidence: { level: 'certain', basis: 'llm' } },
        validInsight,
      ],
    });
    expect(result?.insights).toHaveLength(1);
  });

  it('rejects texts containing internal identifiers', () => {
    const result = normalizeInsightSummary({
      version: 1,
      generated_at: '2026-07-15T12:00:00+00:00',
      insights: [
        { ...validInsight, summary: 'strategy_id = secret' },
        { ...validInsight, title: 'menu_plan_id leaked' },
      ],
    });
    expect(result?.insights).toEqual([]);
  });

  it('filters unknown evidence and rejects empty evidence', () => {
    const result = normalizeInsightSummary({
      version: 1,
      generated_at: '2026-07-15T12:00:00+00:00',
      insights: [
        {
          ...validInsight,
          evidence: { sources: ['raw.event_id'] },
        },
        {
          ...validInsight,
          evidence: {
            sources: ['trend.replacement_rate', 'raw.value'],
          },
        },
      ],
    });
    expect(result?.insights).toHaveLength(1);
    expect(result?.insights[0].evidence.sources).toEqual([
      'trend.replacement_rate',
    ]);
  });

  it('returns null for malformed top-level payloads', () => {
    expect(normalizeInsightSummary(null)).toBeNull();
    expect(normalizeInsightSummary({ insights: [] })).toBeNull();
  });
});

