import type { Profile } from '@/types/profile';
import type { MemorySignal, MemoryPromotionStatus } from '@/types/memory';
import type { BehaviorInsight } from '@/types/behavior';
import type { WorkflowResult } from '@/features/strategy-workflow/types';
import type { StrategyWorkflowError } from '@/features/strategy-workflow/types';

export type SaveProfileSuccess = {
  profile: Profile;
  revision: number;
  updatedAt: string | null;
};

export type ProfileReloadSuccess = {
  profile: Profile;
  revision: number;
};

export type ProfileStaleDetails = {
  currentProfile: Profile;
  currentRevision: number;
};

export type ProfileConflictState = {
  error: StrategyWorkflowError;
  details: ProfileStaleDetails;
};

export type MemorySignalActionSuccess = {
  signalId: string;
  /** Present after reload when the client still has the row locally. */
  signal?: MemorySignal;
  wasConfirmed?: boolean;
};

export type MemoryPromotionSuccess = {
  profile: Profile;
  revision: number;
  promotionStatus: MemoryPromotionStatus;
};

export type BehaviorInsightActionSuccess = {
  insight: BehaviorInsight;
  strategyEffectChanged?: boolean;
  profilePreferenceRemainsActive?: boolean;
  snoozedUntil?: string | null;
};

export type BehaviorRecommendationSuccess = {
  profile: Profile;
  revision: number;
  recommendationStatus: 'applied' | 'already_applied' | 'already_covered' | string;
  recommendationKey: string;
  insight?: BehaviorInsight;
};

export type SaveProfileResult = WorkflowResult<SaveProfileSuccess>;
export type ProfileReloadResult = WorkflowResult<ProfileReloadSuccess>;
export type MemorySignalActionResult = WorkflowResult<MemorySignalActionSuccess>;
export type MemoryPromotionResult = WorkflowResult<MemoryPromotionSuccess>;
export type BehaviorInsightActionResult = WorkflowResult<BehaviorInsightActionSuccess>;
export type BehaviorRecommendationResult = WorkflowResult<BehaviorRecommendationSuccess>;
