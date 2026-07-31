import type {
  BehaviorInsight,
  BehaviorInsightStatus,
  BehaviorInsightType,
  BehaviorInsightsListResponse,
  BehaviorRecommendation,
} from '@/types/behavior';

const VALID_TYPES: readonly BehaviorInsightType[] = [
  'frequent_recipe_replacement',
  'ingredient_availability_friction',
  'high_replacement_rate',
];

/** Active list and action responses may include snoozed/revoked only after action. */
const VALID_STATUSES: readonly BehaviorInsightStatus[] = [
  'candidate',
  'confirmed',
  'snoozed',
  'revoked',
];

function clampConfidence(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  return Math.min(1, Math.max(0, value));
}

function normalizeTimestamp(value: unknown): string {
  if (typeof value !== 'string' || !value.trim()) {
    return '';
  }
  return value;
}

function normalizeRecommendation(value: unknown): BehaviorRecommendation | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  const raw = value as Record<string, unknown>;
  if (
    typeof raw.key !== 'string' ||
    raw.key.trim().length === 0 ||
    typeof raw.can_apply !== 'boolean' ||
    typeof raw.applied !== 'boolean'
  ) {
    return null;
  }
  return {
    key: raw.key.trim(),
    can_apply: raw.can_apply,
    applied: raw.applied,
  };
}

function isBehaviorInsight(value: Record<string, unknown>): boolean {
  const type = value.type;
  const status = value.status;
  return (
    typeof value.id === 'string' &&
    value.id.trim().length > 0 &&
    typeof type === 'string' &&
    VALID_TYPES.includes(type as BehaviorInsightType) &&
    typeof status === 'string' &&
    VALID_STATUSES.includes(status as BehaviorInsightStatus) &&
    typeof value.title === 'string' &&
    value.title.trim().length > 0 &&
    typeof value.description === 'string' &&
    value.description.trim().length > 0 &&
    typeof value.evidence_count === 'number' &&
    typeof value.confidence === 'number' &&
    typeof value.can_confirm === 'boolean' &&
    typeof value.can_dismiss === 'boolean' &&
    typeof value.created_at === 'string' &&
    typeof value.updated_at === 'string'
  );
}

export function normalizeBehaviorInsight(value: unknown): BehaviorInsight | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null;
  }
  const raw = value as Record<string, unknown>;
  if (!isBehaviorInsight(raw)) {
    return null;
  }
  return {
    id: String(raw.id).trim(),
    type: raw.type as BehaviorInsight['type'],
    status: raw.status as BehaviorInsight['status'],
    title: String(raw.title).trim(),
    description: String(raw.description).trim(),
    evidence_count: Math.max(0, Math.floor(Number(raw.evidence_count))),
    confidence: clampConfidence(Number(raw.confidence)),
    can_confirm: Boolean(raw.can_confirm),
    can_dismiss: Boolean(raw.can_dismiss),
    can_snooze: Boolean(raw.can_snooze),
    can_revoke: Boolean(raw.can_revoke),
    created_at: normalizeTimestamp(raw.created_at),
    updated_at: normalizeTimestamp(raw.updated_at),
    recommendation: normalizeRecommendation(raw.recommendation),
    snoozed_until:
      typeof raw.snoozed_until === 'string' && raw.snoozed_until.trim()
        ? raw.snoozed_until
        : null,
    revoked_at:
      typeof raw.revoked_at === 'string' && raw.revoked_at.trim() ? raw.revoked_at : null,
  };
}

/** Safely parses behavior insights API payloads. */
export function normalizeBehaviorInsightsList(
  input: unknown,
): BehaviorInsightsListResponse {
  if (!input || typeof input !== 'object' || Array.isArray(input)) {
    return { insights: [], candidate_count: 0, confirmed_count: 0 };
  }
  const raw = input as Record<string, unknown>;
  const insights = Array.isArray(raw.insights)
    ? raw.insights
        .map(normalizeBehaviorInsight)
        .filter((item): item is BehaviorInsight => item !== null)
        .filter((item) => item.status === 'candidate' || item.status === 'confirmed')
    : [];
  const candidateCount =
    typeof raw.candidate_count === 'number' && raw.candidate_count >= 0
      ? Math.floor(raw.candidate_count)
      : insights.filter((item) => item.status === 'candidate').length;
  const confirmedCount =
    typeof raw.confirmed_count === 'number' && raw.confirmed_count >= 0
      ? Math.floor(raw.confirmed_count)
      : insights.filter((item) => item.status === 'confirmed').length;

  return {
    insights,
    candidate_count: candidateCount,
    confirmed_count: confirmedCount,
  };
}
