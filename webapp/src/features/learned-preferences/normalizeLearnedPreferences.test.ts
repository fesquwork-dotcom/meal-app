import { describe, expect, it } from 'vitest';

import { normalizeLearnedPreferences } from '@/features/learned-preferences/normalizeLearnedPreferences';

const validPreference = {
  id: 'v1:prefer_familiar_meals',
  type: 'prefer_familiar_meals',
  status: 'candidate',
  confidence: 'strong',
  title: 'Знакомые ингредиенты подходят чаще',
  summary: 'Мы заметили, что знакомые блюда подходят вам.',
  evidence: {
    source: 'decision_learning',
    confidence: 'strong',
    basis: 'выбор знакомых блюд',
  },
  version: 1,
  accepted_at: null,
  revoked_at: null,
  planning_effect: 'disabled',
};

describe('normalizeLearnedPreferences', () => {
  it('keeps a valid privacy-safe preference', () => {
    const result = normalizeLearnedPreferences({
      version: 1,
      preferences: [validPreference],
    });
    expect(result?.preferences).toHaveLength(1);
    expect(result?.preferences[0].id).toBe('v1:prefer_familiar_meals');
    expect(result?.preferences[0].evidence.basis).toBe('выбор знакомых блюд');
    expect(result?.preferences[0].planning_effect).toBe('disabled');
  });

  it('fails closed for an unknown planning effect without dropping the card', () => {
    const result = normalizeLearnedPreferences({
      version: 1,
      preferences: [{ ...validPreference, planning_effect: 'guessed' }],
    });
    expect(result?.preferences).toHaveLength(1);
    expect(result?.preferences[0].planning_effect).toBeNull();
  });

  it('drops unknown type, status, confidence, and source', () => {
    const result = normalizeLearnedPreferences({
      version: 1,
      preferences: [
        { ...validPreference, type: 'calorie_target' },
        { ...validPreference, status: 'deleted' },
        { ...validPreference, confidence: 'certain' },
        {
          ...validPreference,
          evidence: { ...validPreference.evidence, source: 'llm' },
        },
        validPreference,
      ],
    });
    expect(result?.preferences).toHaveLength(1);
  });

  it('rejects preferences whose texts leak internal identifiers', () => {
    const result = normalizeLearnedPreferences({
      version: 1,
      preferences: [
        { ...validPreference, summary: 'strategy_id = secret' },
        {
          ...validPreference,
          evidence: { ...validPreference.evidence, basis: 'decision_key leak' },
        },
      ],
    });
    expect(result?.preferences).toEqual([]);
  });

  it('keeps the preference when effectiveness is malformed', () => {
    const result = normalizeLearnedPreferences({
      version: 1,
      preferences: [
        {
          ...validPreference,
          status: 'active',
          effectiveness: { status: 'broken', confidence: 'partial' },
        },
      ],
    });
    expect(result?.preferences).toHaveLength(1);
    expect(result?.preferences[0].effectiveness).toBeNull();
  });

  it('attaches a valid effectiveness payload', () => {
    const result = normalizeLearnedPreferences({
      version: 1,
      preferences: [
        {
          ...validPreference,
          status: 'active',
          last_review_generation: 1,
          effectiveness: {
            status: 'effective',
            confidence: 'established',
            evidence_plans: 4,
            generation: 1,
            title: 'Показывает устойчиво положительный результат',
            summary: 'На нескольких завершённых планах.',
            evidence_text: 'Основано на 4 завершённых планах.',
            limitations: [],
          },
        },
      ],
    });
    expect(result?.preferences[0].effectiveness?.status).toBe('effective');
    expect(result?.preferences[0].effectiveness?.generation).toBe(1);
    expect(result?.preferences[0].last_review_generation).toBe(1);
  });

  it('rejects a preference without valid evidence', () => {
    const result = normalizeLearnedPreferences({
      version: 1,
      preferences: [{ ...validPreference, evidence: { source: 'decision_learning' } }],
    });
    expect(result?.preferences).toEqual([]);
  });

  it('caps the list to ten preferences', () => {
    const result = normalizeLearnedPreferences({
      version: 1,
      preferences: Array.from({ length: 15 }, (_, index) => ({
        ...validPreference,
        id: `v1:pref-${index}`,
      })),
    });
    expect(result?.preferences).toHaveLength(10);
  });

  it('returns null for malformed payloads', () => {
    expect(normalizeLearnedPreferences(null)).toBeNull();
    expect(normalizeLearnedPreferences('nope')).toBeNull();
  });
});
