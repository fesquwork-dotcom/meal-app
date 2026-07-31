import { describe, expect, it } from 'vitest';

import {
  normalizeBehaviorInsight,
  normalizeBehaviorInsightsList,
} from '@/features/behavior/normalizeBehaviorInsights';

const validInsight = {
  id: 'bi_1',
  type: 'frequent_recipe_replacement',
  status: 'candidate',
  title: 'Title',
  description: 'Description',
  evidence_count: 2,
  confidence: 0.6,
  can_confirm: true,
  can_dismiss: true,
  created_at: '2026-07-13T12:00:00+00:00',
  updated_at: '2026-07-13T12:00:00+00:00',
};

describe('normalizeBehaviorInsights', () => {
  it('accepts valid candidate', () => {
    const result = normalizeBehaviorInsight(validInsight);
    expect(result?.status).toBe('candidate');
  });

  it('accepts valid confirmed', () => {
    const result = normalizeBehaviorInsight({ ...validInsight, status: 'confirmed' });
    expect(result?.status).toBe('confirmed');
  });

  it('accepts snoozed and revoked action responses', () => {
    expect(
      normalizeBehaviorInsight({
        ...validInsight,
        status: 'snoozed',
        snoozed_until: '2026-08-01T00:00:00+00:00',
      })?.status,
    ).toBe('snoozed');
    expect(
      normalizeBehaviorInsight({
        ...validInsight,
        status: 'revoked',
        revoked_at: '2026-07-20T00:00:00+00:00',
      })?.status,
    ).toBe('revoked');
  });

  it('filters snoozed and revoked out of active list', () => {
    const result = normalizeBehaviorInsightsList({
      insights: [
        validInsight,
        { ...validInsight, id: 'bi_2', status: 'snoozed' },
        { ...validInsight, id: 'bi_3', status: 'revoked' },
      ],
      candidate_count: 1,
      confirmed_count: 0,
    });
    expect(result.insights).toHaveLength(1);
    expect(result.insights[0]?.id).toBe('bi_1');
  });

  it('rejects unknown type', () => {
    expect(normalizeBehaviorInsight({ ...validInsight, type: 'unknown' })).toBeNull();
  });

  it('rejects unknown status', () => {
    expect(normalizeBehaviorInsight({ ...validInsight, status: 'observed' })).toBeNull();
  });

  it('rejects empty id', () => {
    expect(normalizeBehaviorInsight({ ...validInsight, id: '  ' })).toBeNull();
  });

  it('clamps invalid confidence', () => {
    const result = normalizeBehaviorInsight({ ...validInsight, confidence: 2 });
    expect(result?.confidence).toBe(1);
  });

  it('normalizes negative evidence count', () => {
    const result = normalizeBehaviorInsight({ ...validInsight, evidence_count: -3 });
    expect(result?.evidence_count).toBe(0);
  });

  it('parses list response and drops invalid rows', () => {
    const result = normalizeBehaviorInsightsList({
      insights: [validInsight, { id: '' }],
      candidate_count: 1,
      confirmed_count: 0,
    });
    expect(result.insights).toHaveLength(1);
    expect(result.candidate_count).toBe(1);
  });

  it('returns empty list for invalid payload', () => {
    expect(normalizeBehaviorInsightsList(null)).toEqual({
      insights: [],
      candidate_count: 0,
      confirmed_count: 0,
    });
  });
});
