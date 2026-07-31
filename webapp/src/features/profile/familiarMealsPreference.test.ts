import { describe, expect, it } from 'vitest';

import {
  familiarMealsPreferenceDescription,
  familiarMealsPreferenceFromProfile,
  planningPreferencesFromFamiliarMealsValue,
} from '@/features/profile/familiarMealsPreference';
import {
  buildAppliedPlanningSettingsViewModel,
  buildPreviewPlanningPreferenceLine,
} from '@/features/strategy/appliedPlanningSettingsViewModel';
import { getBehaviorRecommendationCapability } from '@/features/behavior/behaviorInfluence';
import {
  buildBehaviorInsightCardModel,
} from '@/features/behavior/behaviorInsightsViewModel';
import type { BehaviorInsight } from '@/types/behavior';

function insight(overrides: Partial<BehaviorInsight> = {}): BehaviorInsight {
  return {
    id: 'bi_1',
    type: 'high_replacement_rate',
    status: 'confirmed',
    title: 'Вы часто меняете блюда в готовом плане',
    description: 'Мы заметили частые замены.',
    evidence_count: 5,
    confidence: 1,
    can_confirm: false,
    can_dismiss: false,
    can_snooze: false,
    can_revoke: true,
    created_at: '2026-07-13T12:00:00+00:00',
    updated_at: '2026-07-13T12:00:00+00:00',
    ...overrides,
  };
}

describe('familiarMealsPreference', () => {
  it('maps tri-state profile values', () => {
    expect(familiarMealsPreferenceFromProfile({ prefer_familiar_meals: null })).toBe('unset');
    expect(familiarMealsPreferenceFromProfile({ prefer_familiar_meals: true })).toBe('enabled');
    expect(familiarMealsPreferenceFromProfile({ prefer_familiar_meals: false })).toBe('disabled');
  });

  it('round-trips tri-state selections', () => {
    for (const value of ['unset', 'enabled', 'disabled'] as const) {
      const prefs = planningPreferencesFromFamiliarMealsValue(value);
      expect(familiarMealsPreferenceFromProfile(prefs)).toBe(value);
    }
  });

  it('describes each option', () => {
    expect(familiarMealsPreferenceDescription('enabled')).toContain('знаком');
  });
});

describe('appliedPlanningSettingsViewModel', () => {
  it('builds week page lines for profile source', () => {
    const vm = buildAppliedPlanningSettingsViewModel({
      prefer_familiar_meals: true,
      familiar_meals_source: 'profile',
    });
    expect(vm.preferenceLine).toContain('включено');
    expect(vm.sourceLine).toContain('профиле');
  });

  it('builds preview line only when enabled in profile', () => {
    expect(
      buildPreviewPlanningPreferenceLine({
        prefer_familiar_meals: true,
        familiar_meals_source: 'profile',
      }),
    ).toBe('Более знакомые блюда — включено в профиле');
    expect(
      buildPreviewPlanningPreferenceLine({
        prefer_familiar_meals: false,
        familiar_meals_source: 'default',
      }),
    ).toBeNull();
  });
});

describe('behavior recommendation view model', () => {
  it('exposes recommendation action for confirmed high-rate insight', () => {
    const card = buildBehaviorInsightCardModel(
      insight({
        recommendation: { key: 'prefer_familiar_meals', can_apply: true, applied: false },
      }),
    );
    expect(card.canApplyRecommendation).toBe(true);
    expect(card.recommendationActionLabel).toContain('знакомые');
    expect(card.recommendationApplied).toBe(false);
  });

  it('hides recommendation action when already applied', () => {
    const card = buildBehaviorInsightCardModel(
      insight({
        recommendation: { key: 'prefer_familiar_meals', can_apply: false, applied: true },
      }),
    );
    expect(card.canApplyRecommendation).toBe(false);
    expect(card.recommendationApplied).toBe(true);
  });

  it('does not expose recommendation for availability insight', () => {
    const card = buildBehaviorInsightCardModel(
      insight({
        type: 'ingredient_availability_friction',
        recommendation: null,
      }),
    );
    expect(card.recommendationPrompt).toBeNull();
  });

  it('maps recommendation capability helper', () => {
    expect(getBehaviorRecommendationCapability('high_replacement_rate')).toBe(
      'can_enable_familiar_meals',
    );
    expect(getBehaviorRecommendationCapability('frequent_recipe_replacement')).toBe('stored_only');
    expect(getBehaviorRecommendationCapability('ingredient_availability_friction')).toBe(
      'already_applies',
    );
  });
});
