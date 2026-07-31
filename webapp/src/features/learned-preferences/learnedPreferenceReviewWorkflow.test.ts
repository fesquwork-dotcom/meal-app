import { describe, expect, it, vi } from 'vitest';

import {
  keepLearnedPreferenceReview,
  revokeFromLearnedPreferenceReview,
} from '@/features/learned-preferences/learnedPreferenceReviewWorkflow';

vi.mock('@/api/learnedPreferences', () => ({
  dismissLearnedPreferenceReview: vi.fn(async (preferenceId: string) => ({
    version: 1,
    preferences: [
      {
        id: preferenceId,
        type: 'prefer_familiar_meals',
        status: 'active',
        confidence: 'strong',
        title: 'Знакомые',
        summary: 'summary',
        evidence: {
          source: 'decision_learning',
          confidence: 'strong',
          basis: 'basis',
        },
        version: 1,
        accepted_at: '2026-07-12T09:00:00+00:00',
        revoked_at: null,
        last_review_generation: 1,
        effectiveness: {
          status: 'ineffective',
          confidence: 'established',
          evidence_plans: 4,
          generation: 1,
          title: 'Стоит проверить',
          summary: '…',
          evidence_text: '…',
          limitations: [],
        },
      },
    ],
  })),
}));

vi.mock('@/features/learned-preferences/learnedPreferenceWorkflow', () => ({
  revokePreference: vi.fn(async (preferenceId: string) => ({
    ok: true as const,
    data: {
      action: 'revoke' as const,
      preferenceId,
      result: { version: 1, preferences: [] },
    },
  })),
}));

describe('learnedPreferenceReviewWorkflow', () => {
  it('keep calls dismiss-review API and does not call revoke', async () => {
    const { dismissLearnedPreferenceReview } = await import(
      '@/api/learnedPreferences'
    );
    const { revokePreference } = await import(
      '@/features/learned-preferences/learnedPreferenceWorkflow'
    );
    const outcome = await keepLearnedPreferenceReview(
      'v1:prefer_familiar_meals',
    );
    expect(dismissLearnedPreferenceReview).toHaveBeenCalledWith(
      'v1:prefer_familiar_meals',
    );
    expect(revokePreference).not.toHaveBeenCalled();
    expect(outcome.ok).toBe(true);
    if (outcome.ok) {
      expect(outcome.data.action).toBe('keep');
      expect(outcome.data.result.preferences[0].last_review_generation).toBe(1);
    }
  });

  it('revoke uses the existing revoke workflow', async () => {
    const { revokePreference } = await import(
      '@/features/learned-preferences/learnedPreferenceWorkflow'
    );
    const outcome = await revokeFromLearnedPreferenceReview(
      'v1:prefer_familiar_meals',
    );
    expect(revokePreference).toHaveBeenCalledWith('v1:prefer_familiar_meals');
    expect(outcome.ok).toBe(true);
  });
});
