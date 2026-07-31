import { describe, expect, it } from 'vitest';
import { normalizeLearningRecommendations } from '@/features/learning/normalizeLearningRecommendations';

const candidate = {
  recommendation_id: 'rec-1',
  recommendation_type: 'profile_enable_prefer_familiar_meals',
  decision_key: 'planning.prefer_familiar_meals',
  status: 'candidate',
  confidence: 'strong',
  created_at: '2026-07-15T00:00:00+00:00',
  title: 'Попробовать знакомые блюда',
  summary: 'Последний план часто требовал замен.',
  reason: 'Результат плана показал высокую долю замен.',
  expected_effect: 'Это может уменьшить число замен.',
  what_will_not_change: 'Текущий план не изменится.',
  recommended_profile_patch: {
    planning_preferences: { prefer_familiar_meals: true },
  },
  rule_version: 1,
};

describe('normalizeLearningRecommendations', () => {
  it('normalizes empty, candidate, and accepted states', () => {
    expect(
      normalizeLearningRecommendations({
        version: 1,
        candidate_count: 0,
        accepted_count: 0,
        recommendations: [],
      })?.recommendations,
    ).toEqual([]);

    const result = normalizeLearningRecommendations({
      version: 1,
      recommendations: [candidate, { ...candidate, recommendation_id: 'rec-2', status: 'accepted' }],
    });
    expect(result?.candidate_count).toBe(1);
    expect(result?.accepted_count).toBe(1);
  });

  it('filters dismissed and expired history rows', () => {
    const result = normalizeLearningRecommendations({
      recommendations: [
        { ...candidate, status: 'dismissed' },
        { ...candidate, recommendation_id: 'rec-2', status: 'expired' },
      ],
    });
    expect(result?.recommendations).toEqual([]);
  });

  it('rejects unknown types, keys, confidence, and empty patches', () => {
    const result = normalizeLearningRecommendations({
      recommendations: [
        { ...candidate, recommendation_type: 'change_everything' },
        { ...candidate, decision_key: 'protein.excluded' },
        { ...candidate, confidence: 'magic' },
        { ...candidate, recommended_profile_patch: { raw: true } },
      ],
    });
    expect(result?.recommendations).toEqual([]);
  });

  it('rejects texts containing internal evidence fields', () => {
    const result = normalizeLearningRecommendations({
      recommendations: [
        { ...candidate, reason: 'event_key private-event' },
        { ...candidate, title: 'meal_id abc' },
        { ...candidate, summary: 'trace_json payload' },
      ],
    });
    expect(result?.recommendations).toEqual([]);
  });

  it('limits recommendation arrays', () => {
    const result = normalizeLearningRecommendations({
      recommendations: Array.from({ length: 20 }, (_, index) => ({
        ...candidate,
        recommendation_id: `rec-${index}`,
      })),
    });
    expect(result?.recommendations).toHaveLength(10);
  });
});
