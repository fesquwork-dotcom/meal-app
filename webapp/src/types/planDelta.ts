/**
 * Sprint 7.4 — Plan Delta types.
 * Factual differences between the immutable original snapshot and the
 * current validated revision of one durable plan. Read-only.
 */

export type PlanDeltaMetricId =
  | 'total_cost'
  | 'basket_cost'
  | 'changed_meals'
  | 'cooking_time_minutes'
  | 'cooking_sessions'
  | 'calories'
  | 'protein_grams'
  | 'fat_grams'
  | 'carbs_grams';

export type PlanDeltaMetricStatus = 'available' | 'unavailable';

export type PlanDeltaDirection = 'increased' | 'decreased' | 'unchanged';

export type PlanDeltaUnit = 'rub' | 'count' | 'minutes' | 'kcal' | 'grams';

export interface PlanDeltaMetric {
  id: PlanDeltaMetricId;
  status: PlanDeltaMetricStatus;
  unit: PlanDeltaUnit;
  original: number | null;
  current: number | null;
  delta: number | null;
  direction: PlanDeltaDirection | null;
}

export interface PlanDelta {
  version: number;
  metrics: PlanDeltaMetric[];
}

export interface PlanDeltaResult {
  menu_plan_id: string;
  revision: number;
  has_replacements: boolean;
  delta: PlanDelta;
}
