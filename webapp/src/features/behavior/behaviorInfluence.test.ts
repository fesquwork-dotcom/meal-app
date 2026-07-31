import { describe, expect, it } from 'vitest';

import { getBehaviorInfluenceStatus, getBehaviorRecommendationCapability } from '@/features/behavior/behaviorInfluence';
import {
  buildAppliedBehaviorSettingsLine,
  buildPreviewBehaviorLine,
} from '@/features/strategy/appliedBehaviorSettingsViewModel';

describe('behaviorInfluence', () => {
  it('marks availability as strategy-applicable', () => {
    expect(getBehaviorInfluenceStatus('ingredient_availability_friction')).toBe(
      'applies_to_strategy',
    );
  });

  it('marks recipe and high-rate as stored only', () => {
    expect(getBehaviorInfluenceStatus('frequent_recipe_replacement')).toBe('stored_only');
    expect(getBehaviorInfluenceStatus('high_replacement_rate')).toBe('stored_only');
  });

  it('maps recommendation capability by insight type', () => {
    expect(getBehaviorRecommendationCapability('high_replacement_rate')).toBe(
      'can_enable_familiar_meals',
    );
    expect(getBehaviorRecommendationCapability('ingredient_availability_friction')).toBe(
      'already_applies',
    );
  });
});

describe('appliedBehaviorSettingsViewModel', () => {
  it('hides line when applied count is zero', () => {
    expect(buildAppliedBehaviorSettingsLine({ applied_count: 0, ignored_count: 1, availability_preferences_applied: false })).toBeNull();
  });

  it('shows availability line in preview and week page', () => {
    const settings = {
      applied_count: 1,
      ignored_count: 0,
      availability_preferences_applied: true,
    };
    expect(buildPreviewBehaviorLine(settings)).toBe(
      'Учтено подтверждённое наблюдение о доступности продуктов',
    );
    expect(buildAppliedBehaviorSettingsLine(settings)).toBe(
      'Учтено подтверждённое наблюдение о доступности продуктов',
    );
  });
});
