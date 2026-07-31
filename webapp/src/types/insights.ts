/** Sprint 8.1 — privacy-safe deterministic Insight Summary types. */

export type InsightId =
  | 'replacement_health'
  | 'replacement_cost'
  | 'preference_stability'
  | 'recommendation_effectiveness'
  | 'positive_completion';

export type InsightCategory =
  | 'progress'
  | 'consistency'
  | 'adaptation'
  | 'planning'
  | 'cost';

export type InsightStatus = 'insufficient_data' | 'informational' | 'confirmed';
export type InsightConfidenceLevel = 'low' | 'medium' | 'high';
export type InsightConfidenceBasis = 'trend' | 'outcome' | 'delta' | 'none';

export type InsightEvidenceSource =
  | 'trend.replacement_rate'
  | 'trend.decision_health'
  | 'trend.preference_stability'
  | 'trend.recommendation_effectiveness'
  | 'trend.positive_completion'
  | 'outcome.successful'
  | 'delta.total_cost';

export interface InsightConfidence {
  level: InsightConfidenceLevel;
  basis: InsightConfidenceBasis;
}

/** Sprint 8.2 — evidence coverage and transparency. */

export type EvidenceCoverageStatus = 'insufficient' | 'partial' | 'complete';

export type InsightLimitation =
  | 'legacy_strategies'
  | 'positive_events_missing'
  | 'not_enough_completed_plans'
  | 'budget_data_unavailable'
  | 'menuplan_not_persisted'
  | 'decision_snapshot_missing'
  | 'outcome_snapshot_missing';

export type UnavailableReason =
  | 'need_more_completed_plans'
  | 'need_positive_events'
  | 'need_outcomes'
  | 'need_replacements'
  | 'metric_not_supported'
  | 'feature_not_available';

export interface EvidenceCoverage {
  status: EvidenceCoverageStatus;
  available_since: string | null;
  oldest_plan_date: string | null;
  newest_plan_date: string | null;
}

export interface InsightEvidence {
  sources: InsightEvidenceSource[];
  evidence_weeks: number;
  completed_strategies: number;
  positive_events: number;
  replacement_events: number;
  decision_outcomes: number;
  coverage: EvidenceCoverage | null;
  limitations: InsightLimitation[];
  unavailable_reasons: UnavailableReason[];
}

export interface InsightTransparency {
  title: string;
  proof_text: string;
  coverage_text: string;
  availability_text: string | null;
  limitations_text: string[];
}

export interface Insight {
  id: InsightId;
  title: string;
  summary: string;
  category: InsightCategory;
  confidence: InsightConfidence;
  status: InsightStatus;
  evidence: InsightEvidence;
  available_since: string;
  transparency: InsightTransparency | null;
}

export interface InsightSummary {
  version: number;
  generated_at: string;
  insights: Insight[];
}

