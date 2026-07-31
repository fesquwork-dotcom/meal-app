import type { DecisionExplanationCollection } from '@/types/decisionExplanation';
import type { DecisionOutcomeSummary } from '@/types/decisionOutcome';

export type CookingPreferenceSource =
  | 'profile'
  | 'learned_preference'
  | 'memory'
  | 'default'
  | 'inferred';

export type FamiliarMealsSource =
  | 'profile'
  | 'learned_preference'
  | 'default'
  | 'inferred';

export interface AppliedPlanningSettings {
  prefer_familiar_meals: boolean;
  familiar_meals_source: FamiliarMealsSource;
}

export interface AppliedCookingSettings {
  cooking_time_limit: number;
  prefer_faster_meals: boolean;
  preference_source: CookingPreferenceSource;
}

export interface AppliedBehaviorSettings {
  applied_count: number;
  ignored_count: number;
  availability_preferences_applied: boolean;
}

export interface AppliedSettings {
  cooking: AppliedCookingSettings;
  behavior?: AppliedBehaviorSettings | null;
  planning?: AppliedPlanningSettings | null;
}

/** Weekly strategy returned by GET /api/strategy/current. */
export interface WeeklyStrategy {
  strategy_version: number;
  goal: string;
  days: number;
  budget: number;
  meal_types: string[];
  cook_days: number[];
  shopping_days: number[];
  leftovers_enabled: boolean;
  repeat_breakfasts: boolean;
  repeat_lunches: boolean;
  repeat_dinners: boolean;
  preferred_proteins: string[];
  excluded_products: string[];
  cooking_time_limit: number;
  prefer_familiar_meals?: boolean;
  generated_at?: string;
}

export interface StrategyReason {
  code: string;
  title: string;
  description: string;
  category: string;
  priority: number;
  related_days?: number[];
}

export interface StrategyExplanation {
  version: number;
  source?: 'recorded' | 'inferred';
  headline: string;
  summary: string;
  reasons: StrategyReason[];
}

export type StrategyLifecycleStatus = 'none' | 'active' | 'completed' | 'superseded';

export interface CurrentStrategyResponse {
  status: StrategyLifecycleStatus;
  strategy_id: string | null;
  plan_start_date: string | null;
  plan_end_date: string | null;
  strategy: WeeklyStrategy | null;
  explanation: StrategyExplanation | null;
  decision_explanations?: DecisionExplanationCollection | null;
  decision_outcomes?: DecisionOutcomeSummary | null;
  applied_settings?: AppliedSettings | null;
}

export interface StrategyByIdResponse {
  strategy_id: string;
  status: StrategyLifecycleStatus;
  plan_start_date: string;
  plan_end_date: string;
  strategy: WeeklyStrategy;
  explanation: StrategyExplanation | null;
  decision_explanations?: DecisionExplanationCollection | null;
  decision_outcomes?: DecisionOutcomeSummary | null;
  applied_settings?: AppliedSettings | null;
}
