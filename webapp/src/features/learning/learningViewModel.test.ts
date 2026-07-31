import { describe, expect, it } from 'vitest';
import {
  applyLearningPatch,
  buildLearningCardViewModel,
} from '@/features/learning/learningViewModel';
import type { LearningRecommendation } from '@/types/learning';
import type { Profile } from '@/types/profile';

const recommendation: LearningRecommendation = {
  recommendation_id: 'rec-1',
  recommendation_type: 'profile_enable_prefer_familiar_meals',
  decision_key: 'planning.prefer_familiar_meals',
  status: 'candidate',
  confidence: 'strong',
  created_at: null,
  title: 'Попробовать знакомые блюда',
  summary: 'Последний план часто требовал замен.',
  reason: 'Высокая доля замен.',
  expected_effect: 'Меньше замен.',
  what_will_not_change: 'Текущий план не изменится.',
  recommended_profile_patch: {
    planning_preferences: { prefer_familiar_meals: true },
  },
  rule_version: 1,
};

const profile = {
  planning_preferences: { prefer_familiar_meals: false },
  cooking_preferences: { prefer_faster_meals: false },
  cooktime: 'medium',
} as Profile;

describe('learning view model', () => {
  it('builds compact candidate and accepted cards', () => {
    expect(buildLearningCardViewModel(recommendation)).toMatchObject({
      title: 'Попробовать знакомые блюда',
      actionLabel: 'Посмотреть',
      dismissLabel: 'Не сейчас',
    });
    expect(
      buildLearningCardViewModel({ ...recommendation, status: 'accepted' }).actionLabel,
    ).toBe('Применить настройку');
  });

  it('merges only the recommended field without mutating Profile', () => {
    const result = applyLearningPatch(
      profile,
      recommendation.recommended_profile_patch,
    );
    expect(result.planning_preferences.prefer_familiar_meals).toBe(true);
    expect(result.cooking_preferences).toEqual(profile.cooking_preferences);
    expect(result.cooktime).toBe('medium');
    expect(profile.planning_preferences.prefer_familiar_meals).toBe(false);
  });

  it('supports faster and cooktime allowlisted patches', () => {
    const result = applyLearningPatch(profile, {
      cooking_preferences: { prefer_faster_meals: true },
      cooktime: 'slow',
    });
    expect(result.cooking_preferences.prefer_faster_meals).toBe(true);
    expect(result.cooktime).toBe('slow');
    expect(result.planning_preferences).toEqual(profile.planning_preferences);
  });
});
