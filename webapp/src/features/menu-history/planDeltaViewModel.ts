import type { PlanDeltaMetric, PlanDeltaMetricId, PlanDeltaResult } from '@/types/planDelta';

const METRIC_LABELS: Record<PlanDeltaMetricId, string> = {
  total_cost: 'Стоимость плана',
  basket_cost: 'Стоимость корзины',
  changed_meals: 'Заменено блюд',
  cooking_time_minutes: 'Время готовки',
  cooking_sessions: 'Приготовлений',
  calories: 'Калорийность',
  protein_grams: 'Белки',
  fat_grams: 'Жиры',
  carbs_grams: 'Углеводы',
};

const UNIT_SUFFIXES: Record<PlanDeltaMetric['unit'], string> = {
  rub: ' ₽',
  count: '',
  minutes: ' мин',
  kcal: ' ккал',
  grams: ' г',
};

function formatValue(value: number, unit: PlanDeltaMetric['unit']): string {
  const rounded = Math.round(value * 10) / 10;
  return `${rounded}${UNIT_SUFFIXES[unit]}`;
}

function formatSignedDelta(delta: number, unit: PlanDeltaMetric['unit']): string {
  const sign = delta > 0 ? '+' : '−';
  return `${sign}${formatValue(Math.abs(delta), unit)}`;
}

export interface PlanDeltaLineViewModel {
  id: PlanDeltaMetricId;
  label: string;
  /** «2700 ₽ → 2450 ₽» for pair metrics, «2» for count-only metrics. */
  valueLine: string;
  /** Signed change like «−250 ₽»; null when nothing changed. */
  changeLabel: string | null;
}

export interface PlanDeltaViewModel {
  title: string;
  lines: PlanDeltaLineViewModel[];
  hasChanges: boolean;
}

function buildLine(metric: PlanDeltaMetric): PlanDeltaLineViewModel | null {
  if (metric.status !== 'available' || metric.delta === null) {
    // Honesty gate carried into the UI: unavailable metrics are not shown.
    return null;
  }
  if (metric.id === 'changed_meals') {
    return {
      id: metric.id,
      label: METRIC_LABELS[metric.id],
      valueLine: String(Math.round(metric.delta)),
      changeLabel: null,
    };
  }
  if (metric.original === null || metric.current === null) {
    return null;
  }
  return {
    id: metric.id,
    label: METRIC_LABELS[metric.id],
    valueLine: `${formatValue(metric.original, metric.unit)} → ${formatValue(metric.current, metric.unit)}`,
    changeLabel:
      metric.direction === 'unchanged' ? null : formatSignedDelta(metric.delta, metric.unit),
  };
}

/**
 * Builds the «Изменения после замен» view. Returns null when the plan has no
 * replacements or nothing factual can be shown.
 */
export function buildPlanDeltaViewModel(
  result: PlanDeltaResult | null | undefined,
): PlanDeltaViewModel | null {
  if (!result || !result.has_replacements) {
    return null;
  }
  const lines = result.delta.metrics
    .map(buildLine)
    .filter((line): line is PlanDeltaLineViewModel => line !== null);
  if (lines.length === 0) {
    return null;
  }
  return {
    title: 'Изменения после замен',
    lines,
    hasChanges: lines.some(
      (line) => line.changeLabel !== null || (line.id === 'changed_meals' && line.valueLine !== '0'),
    ),
  };
}
