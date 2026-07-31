import { describe, expect, it } from 'vitest';

import {
  REVIEW_TITLE,
  buildEffectivenessViewModel,
  shouldShowEffectivenessReview,
} from '@/features/learned-preferences/learnedPreferenceEffectivenessViewModel';
import type { LearnedPreference } from '@/types/learnedPreferences';

function preference(
  overrides: Partial<LearnedPreference> = {},
): LearnedPreference {
  return {
    id: 'v1:prefer_familiar_meals',
    type: 'prefer_familiar_meals',
    status: 'active',
    confidence: 'strong',
    title: 'Знакомые ингредиенты',
    summary: 'Краткое описание',
    evidence: {
      source: 'decision_learning',
      confidence: 'strong',
      basis: 'основание',
    },
    version: 1,
    accepted_at: '2026-07-12T09:00:00+00:00',
    revoked_at: null,
    planning_effect: 'applied',
    last_review_generation: null,
    effectiveness: {
      status: 'ineffective',
      confidence: 'established',
      evidence_plans: 4,
      generation: 1,
      title: 'Стоит проверить это предпочтение',
      summary: 'После применения часто требовались замены.',
      evidence_text: 'Основано на 4 завершённых планах.',
      limitations: [],
    },
    ...overrides,
  };
}

describe('learnedPreferenceEffectivenessViewModel', () => {
  it('returns null without effectiveness', () => {
    expect(
      buildEffectivenessViewModel(preference({ effectiveness: null })),
    ).toBeNull();
  });

  it('maps insufficient and emerging titles without review', () => {
    const insufficient = buildEffectivenessViewModel(
      preference({
        effectiveness: {
          status: 'insufficient_data',
          confidence: 'insufficient',
          evidence_plans: 1,
          generation: 0,
          title: 'Пока собираем данные',
          summary: 'Мало планов.',
          evidence_text: 'Пока нет завершённых планов.',
          limitations: [],
        },
      }),
    );
    expect(insufficient?.showReview).toBe(false);

    const emerging = buildEffectivenessViewModel(
      preference({
        effectiveness: {
          status: 'emerging',
          confidence: 'partial',
          evidence_plans: 3,
          generation: 0,
          title: 'Есть первые положительные признаки',
          summary: 'Первые признаки.',
          evidence_text: 'Основано на 3 планах.',
          limitations: [],
        },
      }),
    );
    expect(emerging?.showReview).toBe(false);
  });

  it('shows review for established ineffective when never dismissed', () => {
    expect(buildEffectivenessViewModel(preference())?.showReview).toBe(true);
    expect(buildEffectivenessViewModel(preference())?.title).toBe(REVIEW_TITLE);
  });

  it('hides review after dismiss for the same generation', () => {
    expect(
      shouldShowEffectivenessReview(
        preference({ last_review_generation: 1 }),
      ),
    ).toBe(false);
  });

  it('shows review again when generation advances past dismiss', () => {
    expect(
      shouldShowEffectivenessReview(
        preference({
          last_review_generation: 1,
          effectiveness: {
            status: 'ineffective',
            confidence: 'established',
            evidence_plans: 8,
            generation: 2,
            title: REVIEW_TITLE,
            summary: '…',
            evidence_text: '…',
            limitations: [],
          },
        }),
      ),
    ).toBe(true);
  });
});
