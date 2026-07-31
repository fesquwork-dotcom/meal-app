import { describe, expect, it } from 'vitest';

import {
  buildBehaviorInsightsViewModel,
  buildBehaviorInsightCardModel,
  formatEvidenceLabel,
} from '@/features/behavior/behaviorInsightsViewModel';
import type { BehaviorInsight } from '@/types/behavior';

function insight(overrides: Partial<BehaviorInsight> = {}): BehaviorInsight {
  return {
    id: 'bi_1',
    type: 'frequent_recipe_replacement',
    status: 'candidate',
    title: 'Title',
    description: 'Description',
    evidence_count: 2,
    confidence: 0.6,
    can_confirm: true,
    can_dismiss: true,
    can_snooze: true,
    can_revoke: false,
    created_at: '2026-07-13T12:00:00+00:00',
    updated_at: '2026-07-13T12:00:00+00:00',
    ...overrides,
  };
}

describe('behaviorInsightsViewModel', () => {
  it('groups candidate and confirmed insights', () => {
    const vm = buildBehaviorInsightsViewModel(
      [insight(), insight({ id: 'bi_2', status: 'confirmed', can_confirm: false, can_snooze: false, can_revoke: true })],
      1,
    );
    expect(vm.candidates).toHaveLength(1);
    expect(vm.confirmed).toHaveLength(1);
    expect(vm.hasCandidates).toBe(true);
    expect(vm.hasConfirmed).toBe(true);
  });

  it('uses candidate badge count from API', () => {
    const vm = buildBehaviorInsightsViewModel([], 2);
    expect(vm.candidateCount).toBe(2);
    expect(vm.hasAny).toBe(false);
  });

  it('pluralizes evidence labels', () => {
    expect(formatEvidenceLabel(1)).toBe('Замечено один раз');
    expect(formatEvidenceLabel(3)).toBe('Замечено 3 раза');
    expect(formatEvidenceLabel(5)).toBe('Замечено 5 раз');
  });

  it('uses user-facing status labels', () => {
    const vm = buildBehaviorInsightsViewModel([insight()], 1);
    expect(vm.candidates[0]?.statusLabel).toBe('Нужно ваше подтверждение');
    const recipeConfirmed = buildBehaviorInsightsViewModel(
      [insight({ status: 'confirmed', type: 'frequent_recipe_replacement' })],
      0,
    );
    expect(recipeConfirmed.confirmed[0]?.statusLabel).toBe('Наблюдение подтверждено вами');
    const availabilityConfirmed = buildBehaviorInsightsViewModel(
      [insight({ status: 'confirmed', type: 'ingredient_availability_friction' })],
      0,
    );
    expect(availabilityConfirmed.confirmed[0]?.statusLabel).toBe(
      'Будет учтено при создании следующего плана',
    );
    const highRateConfirmed = buildBehaviorInsightCardModel(
      insight({
        status: 'confirmed',
        type: 'high_replacement_rate',
        recommendation: { key: 'prefer_familiar_meals', can_apply: true, applied: false },
      }),
    );
    expect(highRateConfirmed.recommendationActionLabel).toContain('знакомые');
  });

  it('exposes snooze for candidate and revoke for confirmed', () => {
    const candidate = buildBehaviorInsightCardModel(insight({ can_snooze: true }));
    expect(candidate.canSnooze).toBe(true);
    expect(candidate.canRevoke).toBe(false);

    const confirmedAvailability = buildBehaviorInsightCardModel(
      insight({
        status: 'confirmed',
        type: 'ingredient_availability_friction',
        can_confirm: false,
        can_dismiss: false,
        can_snooze: false,
        can_revoke: true,
      }),
    );
    expect(confirmedAvailability.canRevoke).toBe(true);
    expect(confirmedAvailability.revokeConfirmDescription).toContain('следующие планы');
  });

  it('warns that profile preference remains after high-rate revoke', () => {
    const card = buildBehaviorInsightCardModel(
      insight({
        status: 'confirmed',
        type: 'high_replacement_rate',
        can_confirm: false,
        can_snooze: false,
        can_revoke: true,
        recommendation: { key: 'prefer_familiar_meals', can_apply: false, applied: true },
      }),
    );
    expect(card.revokeConfirmDescription).toContain('останется включённой в профиле');
  });

  it('does not expose confidence in card model', () => {
    const vm = buildBehaviorInsightsViewModel([insight()], 1);
    expect(vm.candidates[0]).not.toHaveProperty('confidence');
  });
});
