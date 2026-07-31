import { describe, expect, it } from 'vitest';

import { buildLearnedPreferencesViewModel } from '@/features/learned-preferences/learnedPreferenceViewModel';
import type {
  LearnedPreference,
  LearnedPreferencesResult,
} from '@/types/learnedPreferences';

function preference(overrides: Partial<LearnedPreference> = {}): LearnedPreference {
  return {
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
    ...overrides,
  };
}

function result(preferences: LearnedPreference[]): LearnedPreferencesResult {
  return { version: 1, preferences };
}

describe('buildLearnedPreferencesViewModel', () => {
  it('maps candidate preferences with confidence labels', () => {
    const model = buildLearnedPreferencesViewModel(result([preference()]));
    expect(model?.title).toBe('Адаптивные предпочтения');
    expect(model?.cards).toHaveLength(1);
    expect(model?.cards[0].status).toBe('candidate');
    expect(model?.cards[0].confidenceLabel).toBe('Высокая уверенность');
    expect(model?.cards[0].usedSinceLabel).toBeNull();
  });

  it('shows the used-since label for active preferences', () => {
    const model = buildLearnedPreferencesViewModel(
      result([
        preference({
          status: 'active',
          confidence: 'moderate',
          accepted_at: '2026-07-12T09:00:00+00:00',
          planning_effect: 'applied',
        }),
      ]),
    );
    expect(model?.cards[0].status).toBe('active');
    expect(model?.cards[0].confidenceLabel).toBe('Средняя уверенность');
    expect(model?.cards[0].usedSinceLabel).toBe(
      'Используется системой с 12 июля 2026',
    );
    expect(model?.cards[0].effectiveness).toBeNull();
  });

  it('attaches effectiveness view model for active preferences', () => {
    const model = buildLearnedPreferencesViewModel(
      result([
        preference({
          status: 'active',
          planning_effect: 'applied',
          accepted_at: '2026-07-12T09:00:00+00:00',
          effectiveness: {
            status: 'neutral',
            confidence: 'established',
            evidence_plans: 4,
            generation: 1,
            title: 'Результаты смешанные',
            summary: 'Смешанные результаты.',
            evidence_text: 'Основано на 4 планах.',
            limitations: [],
          },
        }),
      ]),
    );
    expect(model?.cards[0].effectiveness?.status).toBe('neutral');
    expect(model?.cards[0].effectiveness?.showReview).toBe(false);
  });

  it('distinguishes active lifecycle from disabled planning effect', () => {
    const model = buildLearnedPreferencesViewModel(
      result([
        preference({
          status: 'active',
          planning_effect: 'disabled',
          accepted_at: '2026-07-12T09:00:00+00:00',
        }),
      ]),
    );
    expect(model?.cards[0].usedSinceLabel).toBeNull();
    expect(model?.cards[0].planningEffectLabel).toContain(
      'после включения адаптивного планирования',
    );
  });

  it('hides revoked, archived, and transient accepted preferences', () => {
    const model = buildLearnedPreferencesViewModel(
      result([
        preference({ id: 'v1:a', status: 'revoked' }),
        preference({ id: 'v1:b', status: 'archived' }),
        preference({ id: 'v1:c', status: 'accepted' }),
        preference({ id: 'v1:d', status: 'active', accepted_at: '2026-07-12' }),
      ]),
    );
    expect(model?.cards.map((card) => card.id)).toEqual(['v1:d']);
  });

  it('never exposes technical codes in labels', () => {
    const model = buildLearnedPreferencesViewModel(result([preference()]));
    const card = model?.cards[0];
    expect(card?.confidenceLabel).not.toContain('strong');
    expect(card?.title).not.toContain('decision_learning');
  });

  it('returns null without a result and empty cards for none', () => {
    expect(buildLearnedPreferencesViewModel(null)).toBeNull();
    expect(buildLearnedPreferencesViewModel(result([]))?.cards).toEqual([]);
  });
});
