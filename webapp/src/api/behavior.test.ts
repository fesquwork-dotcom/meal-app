import { describe, expect, it, vi } from 'vitest';

import {
  applyBehaviorRecommendation,
  confirmBehaviorInsight,
  dismissBehaviorInsight,
  getBehaviorInsights,
  revokeBehaviorInsight,
  snoozeBehaviorInsight,
} from '@/api/behavior';

vi.mock('@/api/client', () => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { api } from '@/api/client';

const sampleInsight = {
  id: 'bi_1',
  type: 'frequent_recipe_replacement',
  status: 'candidate',
  title: 'Вы несколько раз заменяли один и тот же рецепт',
  description: 'Мы заметили повторяющиеся замены.',
  evidence_count: 2,
  confidence: 0.6,
  can_confirm: true,
  can_dismiss: true,
  can_snooze: true,
  can_revoke: false,
  created_at: '2026-07-13T12:00:00+00:00',
  updated_at: '2026-07-13T12:00:00+00:00',
};

describe('behavior API client', () => {
  it('loads insights from GET path', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: {
        insights: [sampleInsight],
        candidate_count: 1,
        confirmed_count: 0,
      },
    });

    const result = await getBehaviorInsights();
    expect(api.get).toHaveBeenCalledWith('/api/behavior/insights', { signal: undefined });
    expect(result.insights).toHaveLength(1);
    expect(result.candidate_count).toBe(1);
  });

  it('confirms insight without request body', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: {
        insight: { ...sampleInsight, status: 'confirmed', confidence: 1, can_confirm: false },
      },
    });

    const result = await confirmBehaviorInsight('bi_1');
    expect(api.post).toHaveBeenCalledWith('/api/behavior/insights/bi_1/confirm');
    expect(vi.mocked(api.post).mock.calls[0]?.[1]).toBeUndefined();
    expect(result.status).toBe('confirmed');
  });

  it('dismisses insight without request body', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: {
        insight: { ...sampleInsight, status: 'candidate', can_dismiss: false },
      },
    });

    await dismissBehaviorInsight('bi_1');
    expect(api.post).toHaveBeenCalledWith('/api/behavior/insights/bi_1/dismiss');
    expect(vi.mocked(api.post).mock.calls[0]?.[1]).toBeUndefined();
  });

  it('applies recommendation with expected revision only', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: {
        status: 'applied',
        profile: {
          user_id: 42,
          planning_preferences: { prefer_familiar_meals: true },
        },
        profile_revision: 2,
        recommendation_key: 'prefer_familiar_meals',
      },
    });

    const result = await applyBehaviorRecommendation('bi_1', 1);
    expect(api.post).toHaveBeenCalledWith(
      '/api/behavior/insights/bi_1/apply-recommendation',
      { expected_profile_revision: 1 },
    );
    expect(result.revision).toBe(2);
    expect(result.recommendationStatus).toBe('applied');
    expect(result.profile.planning_preferences.prefer_familiar_meals).toBe(true);
  });

  it('snoozes with duration enum only', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: {
        insight: {
          ...sampleInsight,
          status: 'snoozed',
          can_snooze: false,
          snoozed_until: '2026-08-12T12:00:00+00:00',
        },
      },
    });

    const result = await snoozeBehaviorInsight('bi_1', '30_days');
    expect(api.post).toHaveBeenCalledWith('/api/behavior/insights/bi_1/snooze', {
      duration: '30_days',
    });
    expect(result.status).toBe('snoozed');
    expect(result.snoozed_until).toBe('2026-08-12T12:00:00+00:00');
  });

  it('revokes without request body', async () => {
    vi.mocked(api.post).mockResolvedValue({
      data: {
        insight: {
          ...sampleInsight,
          status: 'revoked',
          can_confirm: false,
          can_dismiss: false,
          can_snooze: false,
          can_revoke: false,
          revoked_at: '2026-07-20T12:00:00+00:00',
        },
        strategy_effect_changed: true,
        profile_preference_remains_active: false,
      },
    });

    const result = await revokeBehaviorInsight('bi_1');
    expect(api.post).toHaveBeenCalledWith('/api/behavior/insights/bi_1/revoke');
    expect(vi.mocked(api.post).mock.calls.at(-1)?.[1]).toBeUndefined();
    expect(result.insight.status).toBe('revoked');
    expect(result.strategy_effect_changed).toBe(true);
  });

  it('normalizes invalid list payloads to empty response', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { insights: [{ id: '' }] } });
    const result = await getBehaviorInsights();
    expect(result.insights).toEqual([]);
  });
});
