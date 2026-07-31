/** Sprint 9.1 — privacy-safe Learned Preference types. */

export type LearnedPreferenceType =
  | 'prefer_familiar_meals'
  | 'avoid_unavailable_products'
  | 'prefer_fast_meals'
  | 'stable_cook_days'
  | 'stable_shopping_days';

export type LearnedPreferenceStatus =
  | 'candidate'
  | 'accepted'
  | 'active'
  | 'revoked'
  | 'archived';

export type LearnedPreferenceSource = 'decision_learning';

export type LearnedPreferenceConfidence = 'moderate' | 'strong';
export type LearnedPreferencePlanningEffect =
  | 'applied'
  | 'disabled'
  | 'unsupported';

export type LearnedPreferenceEffectivenessStatus =
  | 'insufficient_data'
  | 'emerging'
  | 'effective'
  | 'neutral'
  | 'ineffective';

export type LearnedPreferenceEffectivenessConfidence =
  | 'insufficient'
  | 'partial'
  | 'established';

export interface LearnedPreferenceEvidence {
  source: LearnedPreferenceSource;
  confidence: LearnedPreferenceConfidence;
  basis: string;
}

export interface LearnedPreferenceEffectiveness {
  status: LearnedPreferenceEffectivenessStatus;
  confidence: LearnedPreferenceEffectivenessConfidence;
  evidence_plans: number;
  /** Evidence cohort index (plans // 4). Used for review re-show. */
  generation: number;
  title: string;
  summary: string;
  evidence_text: string;
  limitations: string[];
}

export interface LearnedPreference {
  id: string;
  type: LearnedPreferenceType;
  status: LearnedPreferenceStatus;
  confidence: LearnedPreferenceConfidence;
  title: string;
  summary: string;
  evidence: LearnedPreferenceEvidence;
  version: number;
  accepted_at: string | null;
  revoked_at: string | null;
  planning_effect?: LearnedPreferencePlanningEffect | null;
  /** Null for candidates or when evaluation is unavailable. */
  effectiveness?: LearnedPreferenceEffectiveness | null;
  /** Last dismissed review cohort; null = never dismissed. */
  last_review_generation?: number | null;
}

export interface LearnedPreferencesResult {
  version: number;
  preferences: LearnedPreference[];
}
