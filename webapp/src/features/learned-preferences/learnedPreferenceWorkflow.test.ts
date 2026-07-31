import { describe, expect, it } from 'vitest';

import { runLearnedPreferenceAction } from '@/features/learned-preferences/learnedPreferenceWorkflow';
import type { LearnedPreferencesResult } from '@/types/learnedPreferences';

const activeResult: LearnedPreferencesResult = {
  version: 1,
  preferences: [
    {
      id: 'v1:prefer_familiar_meals',
      type: 'prefer_familiar_meals',
      status: 'active',
      confidence: 'strong',
      title: 'Знакомые ингредиенты подходят чаще',
      summary: 'Мы заметили закономерность.',
      evidence: {
        source: 'decision_learning',
        confidence: 'strong',
        basis: 'выбор знакомых блюд',
      },
      version: 1,
      accepted_at: '2026-07-12T09:00:00+00:00',
      revoked_at: null,
    },
  ],
};

describe('runLearnedPreferenceAction', () => {
  it('returns ok with the action metadata on success', async () => {
    const outcome = await runLearnedPreferenceAction(
      'accept',
      'v1:prefer_familiar_meals',
      async () => activeResult,
    );
    expect(outcome.ok).toBe(true);
    if (outcome.ok) {
      expect(outcome.data.action).toBe('accept');
      expect(outcome.data.preferenceId).toBe('v1:prefer_familiar_meals');
      expect(outcome.data.result.preferences[0].status).toBe('active');
    }
  });

  it('classifies a thrown error into a WorkflowResult failure', async () => {
    const outcome = await runLearnedPreferenceAction(
      'revoke',
      'v1:prefer_fast_meals',
      async () => {
        throw new Error('network down');
      },
    );
    expect(outcome.ok).toBe(false);
    if (!outcome.ok) {
      expect(typeof outcome.error.code).toBe('string');
      expect(typeof outcome.error.message).toBe('string');
    }
  });

  it('passes the preference id to the executor', async () => {
    let seen = '';
    await runLearnedPreferenceAction('accept', 'v1:stable_cook_days', async (id) => {
      seen = id;
      return activeResult;
    });
    expect(seen).toBe('v1:stable_cook_days');
  });
});
