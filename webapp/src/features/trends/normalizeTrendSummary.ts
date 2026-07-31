import type {
  TrendConfidence,
  TrendConfidenceStatus,
  TrendMetric,
  TrendMetricAvailability,
  TrendMetricId,
  TrendMetricStatus,
  TrendSummary,
} from '@/types/trends';

const METRIC_IDS = new Set<TrendMetricId>([
  'replacement_rate',
  'positive_completion',
  'decision_health',
  'recommendation_effectiveness',
  'preference_stability',
]);

const METRIC_STATUSES = new Set<TrendMetricStatus>([
  'improving',
  'worsening',
  'stable',
  'volatile',
  'insufficient_data',
]);

const CONFIDENCE_STATUSES = new Set<TrendConfidenceStatus>([
  'insufficient_data',
  'emerging',
  'established',
]);

const AVAILABILITIES = new Set<TrendMetricAvailability>([
  'phase_1',
  'sprint_6_4',
  'sprint_6_5',
  'sprint_6_6',
]);

function objectValue(value: unknown): Record<string, unknown> | null {
  return value != null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function text(value: unknown, limit: number): string | null {
  if (typeof value !== 'string') return null;
  const cleaned = value.trim();
  const technical =
    /\b(?:strategy_id|event_id|event_key|memory_id|behavior_id|recipe_id|revision|decision_context|[A-Z]{3,}_[A-Z0-9_]+)\b/.test(
      cleaned,
    );
  return cleaned && cleaned.length <= limit && !technical ? cleaned : null;
}

function count(value: unknown): number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : 0;
}

function normalizeConfidence(value: unknown): TrendConfidence | null {
  const item = objectValue(value);
  if (!item) return null;
  const status = item.status;
  if (typeof status !== 'string' || !CONFIDENCE_STATUSES.has(status as TrendConfidenceStatus)) {
    return null;
  }
  return {
    status: status as TrendConfidenceStatus,
    weeks: count(item.weeks),
    completed_strategies: count(item.completed_strategies),
  };
}

function normalizeMetric(value: unknown): TrendMetric | null {
  const item = objectValue(value);
  if (!item) return null;
  const id = item.id;
  const status = item.status;
  const availability = item.available_since;
  const title = text(item.title, 80);
  const source = text(item.source, 80);
  const summaryText = text(item.summary_text, 200);
  const capabilityNote =
    item.capability_note == null ? null : text(item.capability_note, 200);
  const confidence = normalizeConfidence(item.confidence);
  if (
    typeof id !== 'string' ||
    !METRIC_IDS.has(id as TrendMetricId) ||
    typeof status !== 'string' ||
    !METRIC_STATUSES.has(status as TrendMetricStatus) ||
    typeof availability !== 'string' ||
    !AVAILABILITIES.has(availability as TrendMetricAvailability) ||
    !title ||
    !source ||
    !summaryText ||
    !confidence
  ) {
    return null;
  }

  // Confidence gate is enforced client-side too: quantitative fields are
  // dropped unless the metric is established.
  const established = confidence.status === 'established';
  const rawValue = typeof item.value === 'string' ? item.value.trim() : null;
  const valueSafe =
    established && rawValue && /^[+-]?\d{1,4}%$/.test(rawValue) ? rawValue : null;
  const rawChange = item.change;
  const changeSafe =
    established &&
    typeof rawChange === 'number' &&
    Number.isInteger(rawChange) &&
    rawChange >= -100 &&
    rawChange <= 1000
      ? rawChange
      : null;

  return {
    id: id as TrendMetricId,
    title,
    status: status as TrendMetricStatus,
    value: valueSafe,
    change: changeSafe,
    evidence_weeks: count(item.evidence_weeks),
    confidence,
    source,
    available_since: availability as TrendMetricAvailability,
    summary_text: summaryText,
    capability_note: capabilityNote,
  };
}

export function normalizeTrendSummary(value: unknown): TrendSummary | null {
  const summary = objectValue(value);
  if (!summary) return null;
  const confidence = normalizeConfidence(summary.confidence);
  const generatedAt = typeof summary.generated_at === 'string' ? summary.generated_at : null;
  if (!confidence || !generatedAt) return null;
  const metrics = Array.isArray(summary.metrics)
    ? summary.metrics
        .map(normalizeMetric)
        .filter((item): item is TrendMetric => item !== null)
        .slice(0, 10)
    : [];
  return {
    version: count(summary.version) || 1,
    generated_at: generatedAt,
    confidence,
    metrics,
  };
}
