import type {
  StrategyExplanation,
  AppliedCookingSettings,
  AppliedBehaviorSettings,
  AppliedPlanningSettings,
} from '@/types/strategy';
import type { DecisionExplanationCollection } from '@/types/decisionExplanation';

export type StrategyPreviewStatus = 'ready' | 'conflict';
export type ConflictSeverity = 'blocking' | 'warning';

export type ConflictResolutionAction =
  | 'dismiss_memory_signal'
  | 'remove_profile_protein'
  | 'remove_profile_preference';

export interface ConflictResolutionOption {
  action: string;
  label: string;
  description: string | null;
}

export interface StrategyConflict {
  conflict_id: string;
  code: string;
  title: string;
  description: string;
  severity: ConflictSeverity;
  field: string | null;
  options: ConflictResolutionOption[];
}

export interface AppliedMemorySummary {
  has_applied_signals: boolean;
  applied_count: number;
  ignored_count: number;
  types: string[];
}

export interface StrategyPreviewStrategy {
  days: number;
  cooking_time_limit: number;
  cook_days: number[];
  excluded_products: string[];
  preferred_proteins: string[];
}

export interface AppliedSettingsPreview {
  cooking: AppliedCookingSettings;
  behavior?: AppliedBehaviorSettings | null;
  planning?: AppliedPlanningSettings | null;
}

export interface StrategyPreviewResponse {
  status: StrategyPreviewStatus;
  preview_version: number;
  strategy: StrategyPreviewStrategy | null;
  explanation: StrategyExplanation | null;
  decision_explanations?: DecisionExplanationCollection | null;
  conflicts: StrategyConflict[];
  warnings: StrategyConflict[];
  memory_summary: AppliedMemorySummary | null;
  applied_settings?: AppliedSettingsPreview | null;
  preview_token: string | null;
  preview_expires_at: string | null;
  memory_unavailable: boolean;
}

export interface ResolveConflictRequest {
  preview_token: string;
  conflict_id: string;
  action: ConflictResolutionAction;
}

export interface ResolveConflictResponse {
  status: 'resolved' | 'requires_input';
  profile_revision?: number | null;
  requires_new_preview: boolean;
  code?: string | null;
  field?: string | null;
  message?: string | null;
}
