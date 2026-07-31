/**
 * Sprint 9.3 — allowlisted normalization for preference effectiveness.
 * Malformed payloads fail closed to null; the preference card still renders.
 */

import type {
  LearnedPreferenceEffectiveness,
  LearnedPreferenceEffectivenessConfidence,
  LearnedPreferenceEffectivenessStatus,
} from '@/types/learnedPreferences';

const STATUSES = new Set<LearnedPreferenceEffectivenessStatus>([
  'insufficient_data',
  'emerging',
  'effective',
  'neutral',
  'ineffective',
]);

const CONFIDENCES = new Set<LearnedPreferenceEffectivenessConfidence>([
  'insufficient',
  'partial',
  'established',
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
    /\b(?:strategy_id|decision_id|memory_event_id|event_id|behavior_id|meal_id|profile_revision|user_id|decision_key|menu_plan_id|recommendation_id)\b/i;
  return internal.test(text) ? null : text;
}

export function normalizeLearnedPreferenceEffectiveness(
  value: unknown,
): LearnedPreferenceEffectiveness | null {
  if (value == null) return null;
  const item = objectValue(value);
  if (!item) return null;

  const status = item.status;
  const confidence = item.confidence;
  const title = safeText(item.title, 100);
  const summary = safeText(item.summary, 240);
  const evidenceText = safeText(item.evidence_text, 160);
  const evidencePlans = item.evidence_plans;
  const generation = item.generation;

  if (
    typeof status !== 'string' ||
    !STATUSES.has(status as LearnedPreferenceEffectivenessStatus) ||
    typeof confidence !== 'string' ||
    !CONFIDENCES.has(confidence as LearnedPreferenceEffectivenessConfidence) ||
    !title ||
    !summary ||
    !evidenceText ||
    typeof evidencePlans !== 'number' ||
    !Number.isInteger(evidencePlans) ||
    evidencePlans < 0 ||
    evidencePlans > 12 ||
    typeof generation !== 'number' ||
    !Number.isInteger(generation) ||
    generation < 0 ||
    generation > 3
  ) {
    return null;
  }

  const limitations = Array.isArray(item.limitations)
    ? item.limitations
        .map((entry) => safeText(entry, 160))
        .filter((entry): entry is string => entry !== null)
        .slice(0, 6)
    : [];

  // Reject payloads that still carry internal counters / ids.
  if (
    'positive_evidence_count' in item ||
    'negative_evidence_count' in item ||
    'strategy_id' in item ||
    'raw_evidence' in item
  ) {
    return null;
  }

  return {
    status: status as LearnedPreferenceEffectivenessStatus,
    confidence: confidence as LearnedPreferenceEffectivenessConfidence,
    evidence_plans: evidencePlans,
    generation,
    title,
    summary,
    evidence_text: evidenceText,
    limitations,
  };
}
