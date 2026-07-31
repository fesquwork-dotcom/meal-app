import type {
  TrendConfidenceStatus,
  TrendMetric,
  TrendMetricStatus,
  TrendSummary,
} from '@/types/trends';

const STATUS_ICON: Record<TrendMetricStatus, string> = {
  improving: '↗',
  worsening: '↘',
  stable: '→',
  volatile: '↔',
  insufficient_data: '…',
};

const STATUS_LABELS: Record<TrendMetricStatus, string> = {
  improving: 'Улучшается',
  worsening: 'Ухудшается',
  stable: 'Стабильно',
  volatile: 'Часто меняется',
  insufficient_data: 'Недостаточно данных',
};

const CONFIDENCE_LABELS: Record<TrendConfidenceStatus, string> = {
  insufficient_data: 'Недостаточно данных',
  emerging: 'Первые наблюдения',
  established: 'Устойчивая оценка',
};

export interface TrendMetricViewModel {
  id: string;
  icon: string;
  title: string;
  statusLabel: string;
  status: TrendMetricStatus;
  summaryText: string;
  /** Formatted signed percent, only for established metrics. */
  changeLabel: string | null;
  evidenceLabel: string;
  sourceLabel: string;
  confidenceLabel: string;
  capabilityNote: string | null;
}

export interface TrendsViewModel {
  title: string;
  overallLabel: string;
  metrics: TrendMetricViewModel[];
}

function weeksLabel(weeks: number): string {
  if (weeks === 0) return 'нет завершённых недель';
  const mod10 = weeks % 10;
  const mod100 = weeks % 100;
  const noun =
    mod10 === 1 && mod100 !== 11
      ? 'неделя'
      : mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)
        ? 'недели'
        : 'недель';
  return `${weeks} ${noun} наблюдений`;
}

function changeLabel(metric: TrendMetric): string | null {
  // Confidence gate: numbers appear only for established metrics.
  if (metric.confidence.status !== 'established' || metric.change === null) {
    return null;
  }
  const sign = metric.change > 0 ? '+' : '';
  return `${sign}${metric.change}%`;
}

export function buildTrendsViewModel(
  summary: TrendSummary | null | undefined,
): TrendsViewModel | null {
  if (!summary) return null;
  return {
    title: 'Мой прогресс',
    overallLabel: CONFIDENCE_LABELS[summary.confidence.status],
    metrics: summary.metrics.map((metric) => ({
      id: metric.id,
      icon: STATUS_ICON[metric.status],
      title: metric.title,
      statusLabel: STATUS_LABELS[metric.status],
      status: metric.status,
      summaryText: metric.summary_text,
      changeLabel: changeLabel(metric),
      evidenceLabel: weeksLabel(metric.evidence_weeks),
      sourceLabel: `Источник: ${metric.source}`,
      confidenceLabel: CONFIDENCE_LABELS[metric.confidence.status],
      capabilityNote: metric.capability_note,
    })),
  };
}
