export type BehaviorInsightType =
  | 'frequent_recipe_replacement'
  | 'ingredient_availability_friction'
  | 'high_replacement_rate';

export type BehaviorInsightStatus = 'candidate' | 'confirmed' | 'snoozed' | 'revoked';

export type BehaviorSnoozeDuration = '7_days' | '30_days';

export interface BehaviorRecommendation {
  key: string;
  can_apply: boolean;
  applied: boolean;
}

export interface BehaviorInsight {
  id: string;
  type: BehaviorInsightType;
  status: BehaviorInsightStatus;
  title: string;
  description: string;
  evidence_count: number;
  confidence: number;
  can_confirm: boolean;
  can_dismiss: boolean;
  can_snooze: boolean;
  can_revoke: boolean;
  created_at: string;
  updated_at: string;
  recommendation?: BehaviorRecommendation | null;
  snoozed_until?: string | null;
  revoked_at?: string | null;
}

export type BehaviorRecommendationStatus = 'applied' | 'already_applied' | 'already_covered';

export interface ApplyBehaviorRecommendationResponse {
  status: BehaviorRecommendationStatus;
  profile: Record<string, unknown>;
  profile_revision: number;
  recommendation_key: string;
}

export interface BehaviorRevokeResponse {
  insight: BehaviorInsight;
  strategy_effect_changed: boolean;
  profile_preference_remains_active: boolean;
}

export interface BehaviorInsightsListResponse {
  insights: BehaviorInsight[];
  candidate_count: number;
  confirmed_count: number;
}
