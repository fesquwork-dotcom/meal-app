import type {
  DecisionOutcomeStatus,
  DecisionOutcomeSummary,
  OutcomeExplanation,
} from '@/types/decisionOutcome';

const PUBLIC_KEYS = new Set([
  'planning.prefer_familiar_meals',
  'cooking.prefer_faster',
  'behavior.availability_avoid_products',
  'cooking.cook_days',
  'shopping.days',
]);

const STATUSES = new Set<DecisionOutcomeStatus>([
  'pending',
  'successful',
  'neutral',
  'unsuccessful',
  'insufficient_data',
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
    /\b(?:event_key|memory_id|behavior_id|recipe_id|ingredient_id|rule_code|reason_code|[A-Z]{3,}_[A-Z0-9_]+)\b/.test(
      cleaned,
    );
  return cleaned && cleaned.length <= limit && !technical ? cleaned : null;
}

function count(value: unknown): number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : 0;
}

function normalizeExplanation(value: unknown): OutcomeExplanation | null {
  const item = objectValue(value);
  if (!item) return null;
  const decisionKey = text(item.decision_key, 80);
  const title = text(item.title, 80);
  const statusLabel = text(item.status_label, 80);
  const explanation = text(item.explanation, 300);
  const status = item.status;
  if (
    !decisionKey ||
    !PUBLIC_KEYS.has(decisionKey) ||
    !title ||
    !statusLabel ||
    !explanation ||
    typeof status !== 'string' ||
    !STATUSES.has(status as DecisionOutcomeStatus)
  ) {
    return null;
  }
  return {
    decision_key: decisionKey,
    title,
    status: status as DecisionOutcomeStatus,
    status_label: statusLabel,
    explanation,
  };
}

export function normalizeDecisionOutcomes(value: unknown): DecisionOutcomeSummary | null {
  const summary = objectValue(value);
  if (!summary) return null;
  const explanations = Array.isArray(summary.explanations)
    ? summary.explanations
        .map(normalizeExplanation)
        .filter((item): item is OutcomeExplanation => item !== null)
        .slice(0, 5)
    : [];
  return {
    version: count(summary.version) || 1,
    evaluated_count: count(summary.evaluated_count),
    successful_count: count(summary.successful_count),
    neutral_count: count(summary.neutral_count),
    unsuccessful_count: count(summary.unsuccessful_count),
    insufficient_data_count: count(summary.insufficient_data_count),
    pending_count: count(summary.pending_count),
    explanations,
  };
}
