/**
 * Sprint 7.1 — read-only trend summary types.
 * Trends observe history only and never influence decisions.
 */

export type TrendMetricId =
  | 'replacement_rate'
  | 'positive_completion'
  | 'decision_health'
  | 'recommendation_effectiveness'
  | 'preference_stability';

export type TrendMetricStatus =
  | 'improving'
  | 'worsening'
  | 'stable'
  | 'volatile'
  | 'insufficient_data';

export type TrendConfidenceStatus = 'insufficient_data' | 'emerging' | 'established';

export type TrendMetricAvailability =
  | 'phase_1'
  | 'sprint_6_4'
  | 'sprint_6_5'
  | 'sprint_6_6';

export interface TrendConfidence {
  status: TrendConfidenceStatus;
  weeks: number;
  completed_strategies: number;
}

export interface TrendMetric {
  id: TrendMetricId;
  title: string;
  status: TrendMetricStatus;
  /** Present only when confidence is established. */
  value: string | null;
  /** Signed percent change; present only when confidence is established. */
  change: number | null;
  evidence_weeks: number;
  confidence: TrendConfidence;
  source: string;
  available_since: TrendMetricAvailability;
  summary_text: string;
  capability_note: string | null;
}

export interface TrendSummary {
  version: number;
  generated_at: string;
  confidence: TrendConfidence;
  metrics: TrendMetric[];
}
