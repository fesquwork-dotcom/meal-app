export type LearningRecommendationType =
  | 'profile_enable_prefer_familiar_meals'
  | 'profile_disable_prefer_familiar_meals'
  | 'profile_enable_prefer_faster_meals'
  | 'profile_disable_prefer_faster_meals'
  | 'profile_adjust_cooking_time';

export type LearningRecommendationStatus =
  | 'candidate'
  | 'accepted'
  | 'dismissed'
  | 'expired';

export interface RecommendedProfilePatch {
  planning_preferences?: { prefer_familiar_meals: boolean | null } | null;
  cooking_preferences?: { prefer_faster_meals: boolean | null } | null;
  cooktime?: 'fast' | 'medium' | 'slow' | null;
}

export interface LearningRecommendation {
  recommendation_id: string;
  recommendation_type: LearningRecommendationType;
  decision_key: string;
  status: LearningRecommendationStatus;
  confidence: 'moderate' | 'strong';
  created_at: string | null;
  title: string;
  summary: string;
  reason: string;
  expected_effect: string;
  what_will_not_change: string;
  recommended_profile_patch: RecommendedProfilePatch;
  rule_version: number;
}

export interface LearningRecommendationSummary {
  version: number;
  candidate_count: number;
  accepted_count: number;
  recommendations: LearningRecommendation[];
}

export interface LearningAcceptResponse {
  recommendation_id: string;
  status: 'accepted';
  recommended_profile_patch: RecommendedProfilePatch;
}
