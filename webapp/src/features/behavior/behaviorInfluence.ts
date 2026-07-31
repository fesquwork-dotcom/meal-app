import type { BehaviorInsightType } from '@/types/behavior';

export type BehaviorInfluenceStatus = 'applies_to_strategy' | 'stored_only';

export type BehaviorRecommendationCapability =
  | 'already_applies'
  | 'stored_only'
  | 'can_enable_familiar_meals';

const APPLIES_TO_STRATEGY: ReadonlySet<BehaviorInsightType> = new Set([
  'ingredient_availability_friction',
]);

export function getBehaviorInfluenceStatus(type: BehaviorInsightType): BehaviorInfluenceStatus {
  return APPLIES_TO_STRATEGY.has(type) ? 'applies_to_strategy' : 'stored_only';
}

export function getBehaviorRecommendationCapability(
  type: BehaviorInsightType,
): BehaviorRecommendationCapability {
  if (type === 'ingredient_availability_friction') {
    return 'already_applies';
  }
  if (type === 'high_replacement_rate') {
    return 'can_enable_familiar_meals';
  }
  return 'stored_only';
}
