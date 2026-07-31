import type {
  PlanDelta,
  PlanDeltaDirection,
  PlanDeltaMetric,
  PlanDeltaMetricId,
  PlanDeltaUnit,
} from '@/types/planDelta';

const METRIC_IDS = new Set<PlanDeltaMetricId>([
  'total_cost',
  'basket_cost',
  'changed_meals',
  'cooking_time_minutes',
  'cooking_sessions',
  'calories',
  'protein_grams',
  'fat_grams',
  'carbs_grams',
]);

const UNITS = new Set<PlanDeltaUnit>(['rub', 'count', 'minutes', 'kcal', 'grams']);

const DIRECTIONS = new Set<PlanDeltaDirection>(['increased', 'decreased', 'unchanged']);

function objectValue(value: unknown): Record<string, unknown> | null {
  return value != null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function normalizeMetric(value: unknown): PlanDeltaMetric | null {
  const item = objectValue(value);
  if (!item) return null;
  const id = item.id;
  const unit = item.unit;
  if (
    typeof id !== 'string' ||
    !METRIC_IDS.has(id as PlanDeltaMetricId) ||
    typeof unit !== 'string' ||
    !UNITS.has(unit as PlanDeltaUnit)
  ) {
    return null;
  }

  if (item.status !== 'available') {
    return {
      id: id as PlanDeltaMetricId,
      status: 'unavailable',
      unit: unit as PlanDeltaUnit,
      original: null,
      current: null,
      delta: null,
      direction: null,
    };
  }

  const delta = finiteNumber(item.delta);
  const direction = item.direction;
  if (
    delta === null ||
    typeof direction !== 'string' ||
    !DIRECTIONS.has(direction as PlanDeltaDirection)
  ) {
    return null;
  }
  return {
    id: id as PlanDeltaMetricId,
    status: 'available',
    unit: unit as PlanDeltaUnit,
    original: finiteNumber(item.original),
    current: finiteNumber(item.current),
    delta,
    direction: direction as PlanDeltaDirection,
  };
}

export function normalizePlanDelta(value: unknown): PlanDelta | null {
  const payload = objectValue(value);
  if (!payload) return null;
  const metrics = Array.isArray(payload.metrics)
    ? payload.metrics
        .map(normalizeMetric)
        .filter((metric): metric is PlanDeltaMetric => metric !== null)
        .slice(0, 12)
    : [];
  const version = finiteNumber(payload.version);
  return {
    version: version !== null && version >= 1 ? version : 1,
    metrics,
  };
}
