import { normalizeLearnedPreferenceEffectiveness } from '@/features/learned-preferences/normalizeLearnedPreferenceEffectiveness';
import type {
  LearnedPreference,
  LearnedPreferenceConfidence,
  LearnedPreferenceEvidence,
  LearnedPreferencePlanningEffect,
  LearnedPreferenceSource,
  LearnedPreferenceStatus,
  LearnedPreferenceType,
  LearnedPreferencesResult,
} from '@/types/learnedPreferences';

const TYPES = new Set<LearnedPreferenceType>([
  'prefer_familiar_meals',
  'avoid_unavailable_products',
  'prefer_fast_meals',
  'stable_cook_days',
  'stable_shopping_days',
]);
const STATUSES = new Set<LearnedPreferenceStatus>([
  'candidate',
  'accepted',
  'active',
  'revoked',
  'archived',
]);
const SOURCES = new Set<LearnedPreferenceSource>(['decision_learning']);
const CONFIDENCES = new Set<LearnedPreferenceConfidence>(['moderate', 'strong']);
const PLANNING_EFFECTS = new Set<LearnedPreferencePlanningEffect>([
  'applied',
  'disabled',
  'unsupported',
]);

function objectValue(value: unknown): Record<string, unknown> | null {
  return value != null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function safeText(value: unknown, limit: number): string | null {
  if (typeof value !== 'string') return null;
  const text = value.trim();
  if (!text || text.length > limit) return null;
  const internal =
    /\b(?:strategy_id|decision_id|memory_event_id|event_id|behavior_id|meal_id|profile_revision|user_id|decision_key)\b/i;
  return internal.test(text) ? null : text;
}

function isoTimestamp(value: unknown): string | null {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}/.test(value)
    ? value
    : null;
}

function normalizeEvidence(value: unknown): LearnedPreferenceEvidence | null {
  const evidence = objectValue(value);
  if (!evidence) return null;
  const source = evidence.source;
  const confidence = evidence.confidence;
  const basis = safeText(evidence.basis, 80);
  if (
    typeof source !== 'string' ||
    !SOURCES.has(source as LearnedPreferenceSource) ||
    typeof confidence !== 'string' ||
    !CONFIDENCES.has(confidence as LearnedPreferenceConfidence) ||
    !basis
  ) {
    return null;
  }
  return {
    source: source as LearnedPreferenceSource,
    confidence: confidence as LearnedPreferenceConfidence,
    basis,
  };
}

function normalizePreference(value: unknown): LearnedPreference | null {
  const item = objectValue(value);
  if (!item) return null;
  const id = safeText(item.id, 80);
  const type = item.type;
  const status = item.status;
  const confidence = item.confidence;
  const title = safeText(item.title, 100);
  const summary = safeText(item.summary, 240);
  const evidence = normalizeEvidence(item.evidence);
  if (
    !id ||
    typeof type !== 'string' ||
    !TYPES.has(type as LearnedPreferenceType) ||
    typeof status !== 'string' ||
    !STATUSES.has(status as LearnedPreferenceStatus) ||
    typeof confidence !== 'string' ||
    !CONFIDENCES.has(confidence as LearnedPreferenceConfidence) ||
    !title ||
    !summary ||
    !evidence
  ) {
    return null;
  }
  const lastReviewGeneration = item.last_review_generation;
  const normalizedLastReview =
    lastReviewGeneration == null
      ? null
      : typeof lastReviewGeneration === 'number' &&
          Number.isInteger(lastReviewGeneration) &&
          lastReviewGeneration >= 0 &&
          lastReviewGeneration <= 3
        ? lastReviewGeneration
        : null;
  return {
    id,
    type: type as LearnedPreferenceType,
    status: status as LearnedPreferenceStatus,
    confidence: confidence as LearnedPreferenceConfidence,
    title,
    summary,
    evidence,
    version:
      typeof item.version === 'number' && Number.isInteger(item.version) && item.version >= 1
        ? item.version
        : 1,
    accepted_at: isoTimestamp(item.accepted_at),
    revoked_at: isoTimestamp(item.revoked_at),
    planning_effect:
      typeof item.planning_effect === 'string' &&
      PLANNING_EFFECTS.has(
        item.planning_effect as LearnedPreferencePlanningEffect,
      )
        ? (item.planning_effect as LearnedPreferencePlanningEffect)
        : null,
    // Malformed effectiveness fails closed without dropping the preference.
    effectiveness: normalizeLearnedPreferenceEffectiveness(item.effectiveness),
    last_review_generation: normalizedLastReview,
  };
}

export function normalizeLearnedPreferences(
  value: unknown,
): LearnedPreferencesResult | null {
  const payload = objectValue(value);
  if (!payload) return null;
  const preferences = Array.isArray(payload.preferences)
    ? payload.preferences
        .map(normalizePreference)
        .filter((item): item is LearnedPreference => item !== null)
        .slice(0, 10)
    : [];
  return {
    version:
      typeof payload.version === 'number' &&
      Number.isInteger(payload.version) &&
      payload.version >= 1
        ? payload.version
        : 1,
    preferences,
  };
}
