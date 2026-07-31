import type {
  LearningRecommendation,
  LearningRecommendationStatus,
  LearningRecommendationSummary,
  LearningRecommendationType,
  RecommendedProfilePatch,
} from '@/types/learning';

const TYPES = new Set<LearningRecommendationType>([
  'profile_enable_prefer_familiar_meals',
  'profile_disable_prefer_familiar_meals',
  'profile_enable_prefer_faster_meals',
  'profile_disable_prefer_faster_meals',
  'profile_adjust_cooking_time',
]);
const STATUSES = new Set<LearningRecommendationStatus>([
  'candidate',
  'accepted',
  'dismissed',
  'expired',
]);
const PUBLIC_DECISION_KEYS = new Set([
  'planning.prefer_familiar_meals',
  'cooking.prefer_faster',
  'cooking.time_limit',
]);

function record(value: unknown): Record<string, unknown> | null {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

function text(value: unknown, maxLength: number): string | null {
  if (typeof value !== 'string') return null;
  const cleaned = value.trim();
  const internal =
    /\b(?:event_key|meal_id|recipe_id|ingredient_id|trace_json|evidence_json|[A-Z]{3,}_[A-Z0-9_]+)\b/.test(
      cleaned,
    );
  return cleaned && cleaned.length <= maxLength && !internal ? cleaned : null;
}

function count(value: unknown): number {
  return typeof value === 'number' && Number.isInteger(value) && value >= 0 ? value : 0;
}

export function normalizeRecommendedProfilePatch(value: unknown): RecommendedProfilePatch | null {
  const source = record(value);
  if (!source) return null;
  const patch: RecommendedProfilePatch = {};

  const planning = record(source.planning_preferences);
  if (planning && typeof planning.prefer_familiar_meals === 'boolean') {
    patch.planning_preferences = {
      prefer_familiar_meals: planning.prefer_familiar_meals,
    };
  }
  const cooking = record(source.cooking_preferences);
  if (cooking && typeof cooking.prefer_faster_meals === 'boolean') {
    patch.cooking_preferences = {
      prefer_faster_meals: cooking.prefer_faster_meals,
    };
  }
  if (source.cooktime === 'fast' || source.cooktime === 'medium' || source.cooktime === 'slow') {
    patch.cooktime = source.cooktime;
  }

  return Object.keys(patch).length > 0 ? patch : null;
}

function normalizeRecommendation(value: unknown): LearningRecommendation | null {
  const item = record(value);
  if (!item) return null;
  const recommendationId = text(item.recommendation_id, 80);
  const type = item.recommendation_type;
  const decisionKey = text(item.decision_key, 80);
  const status = item.status;
  const confidence = item.confidence;
  const title = text(item.title, 100);
  const summary = text(item.summary, 240);
  const reason = text(item.reason, 300);
  const expectedEffect = text(item.expected_effect, 240);
  const unchanged = text(item.what_will_not_change, 240);
  const patch = normalizeRecommendedProfilePatch(item.recommended_profile_patch);
  const patchMatchesType =
    typeof type === 'string' &&
    ((type === 'profile_enable_prefer_familiar_meals' &&
      patch?.planning_preferences?.prefer_familiar_meals === true &&
      !patch.cooking_preferences &&
      !patch.cooktime) ||
      (type === 'profile_disable_prefer_familiar_meals' &&
        patch?.planning_preferences?.prefer_familiar_meals === false &&
        !patch.cooking_preferences &&
        !patch.cooktime) ||
      (type === 'profile_enable_prefer_faster_meals' &&
        patch?.cooking_preferences?.prefer_faster_meals === true &&
        !patch.planning_preferences &&
        !patch.cooktime) ||
      (type === 'profile_disable_prefer_faster_meals' &&
        patch?.cooking_preferences?.prefer_faster_meals === false &&
        !patch.planning_preferences &&
        !patch.cooktime) ||
      (type === 'profile_adjust_cooking_time' &&
        Boolean(patch?.cooktime) &&
        !patch?.planning_preferences &&
        !patch?.cooking_preferences));
  if (
    !recommendationId ||
    typeof type !== 'string' ||
    !TYPES.has(type as LearningRecommendationType) ||
    !decisionKey ||
    !PUBLIC_DECISION_KEYS.has(decisionKey) ||
    typeof status !== 'string' ||
    !STATUSES.has(status as LearningRecommendationStatus) ||
    (confidence !== 'moderate' && confidence !== 'strong') ||
    !title ||
    !summary ||
    !reason ||
    !expectedEffect ||
    !unchanged ||
    !patch ||
    !patchMatchesType
  ) {
    return null;
  }
  return {
    recommendation_id: recommendationId,
    recommendation_type: type as LearningRecommendationType,
    decision_key: decisionKey,
    status: status as LearningRecommendationStatus,
    confidence,
    created_at: text(item.created_at, 40),
    title,
    summary,
    reason,
    expected_effect: expectedEffect,
    what_will_not_change: unchanged,
    recommended_profile_patch: patch,
    rule_version: count(item.rule_version) || 1,
  };
}

export function normalizeLearningRecommendations(
  value: unknown,
): LearningRecommendationSummary | null {
  const source = record(value);
  if (!source) return null;
  const recommendations = Array.isArray(source.recommendations)
    ? source.recommendations
        .map(normalizeRecommendation)
        .filter((item): item is LearningRecommendation => item !== null)
        .filter((item) => item.status === 'candidate' || item.status === 'accepted')
        .slice(0, 10)
    : [];
  return {
    version: count(source.version) || 1,
    candidate_count: recommendations.filter((item) => item.status === 'candidate').length,
    accepted_count: recommendations.filter((item) => item.status === 'accepted').length,
    recommendations,
  };
}
