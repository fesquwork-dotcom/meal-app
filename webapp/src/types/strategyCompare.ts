import type { StrategyPreviewResponse } from '@/types/strategyPreview';
import type { DecisionExplanationChange } from '@/types/decisionExplanation';

export type ComparisonQuality = 'exact' | 'partial' | 'unavailable';
export type SettingChangeType = 'changed' | 'added' | 'removed' | 'source_changed';

export interface StrategySettingValue {
  display_value: string;
  raw_value?: string | number | boolean | string[] | null;
  source?: string | null;
}

export interface StrategySettingChange {
  key: string;
  category: string;
  change_type: SettingChangeType;
  title: string;
  description: string;
  current: StrategySettingValue | null;
  next: StrategySettingValue | null;
  priority: number;
}

export interface StrategySettingsDiff {
  version: number;
  has_changes: boolean;
  changes: StrategySettingChange[];
  unchanged_count: number;
  comparison_quality: ComparisonQuality;
}

export interface StrategyCompareResponse {
  preview: StrategyPreviewResponse | null;
  diff: StrategySettingsDiff | null;
  decision_changes?: DecisionExplanationChange[] | null;
}

export interface StrategyCompareRequest {
  plan_start_date?: string | null;
}
