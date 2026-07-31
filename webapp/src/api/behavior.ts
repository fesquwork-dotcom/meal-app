import { api } from '@/api/client';
import type { ResourceLoaderOptions } from '@/api/resourceLoaderOptions';
import { normalizeProfile } from '@/features/profile/normalizeProfile';
import { normalizeBehaviorInsight, normalizeBehaviorInsightsList } from '@/features/behavior/normalizeBehaviorInsights';
import type {
  ApplyBehaviorRecommendationResponse,
  BehaviorInsight,
  BehaviorInsightsListResponse,
  BehaviorRevokeResponse,
  BehaviorSnoozeDuration,
} from '@/types/behavior';
import type { LoadedProfile } from '@/api/profile';
import type { ProfileApiRecord } from '@/types/profile';

export async function getBehaviorInsights(
  options?: ResourceLoaderOptions,
): Promise<BehaviorInsightsListResponse> {
  const { data } = await api.get<unknown>('/api/behavior/insights', {
    signal: options?.signal,
  });
  return normalizeBehaviorInsightsList(data);
}

export async function confirmBehaviorInsight(insightId: string): Promise<BehaviorInsight> {
  const { data } = await api.post<unknown>(
    `/api/behavior/insights/${encodeURIComponent(insightId)}/confirm`,
  );
  const payload =
    data && typeof data === 'object' && !Array.isArray(data)
      ? (data as Record<string, unknown>).insight
      : null;
  const insight = normalizeBehaviorInsight(payload);
  if (!insight) {
    throw new Error('Invalid behavior insight confirm response');
  }
  return insight;
}

export async function dismissBehaviorInsight(insightId: string): Promise<BehaviorInsight> {
  const { data } = await api.post<unknown>(
    `/api/behavior/insights/${encodeURIComponent(insightId)}/dismiss`,
  );
  const payload =
    data && typeof data === 'object' && !Array.isArray(data)
      ? (data as Record<string, unknown>).insight
      : null;
  const insight = normalizeBehaviorInsight(payload);
  if (!insight) {
    throw new Error('Invalid behavior insight dismiss response');
  }
  return insight;
}

export async function snoozeBehaviorInsight(
  insightId: string,
  duration: BehaviorSnoozeDuration,
): Promise<BehaviorInsight> {
  const { data } = await api.post<unknown>(
    `/api/behavior/insights/${encodeURIComponent(insightId)}/snooze`,
    { duration },
  );
  const payload =
    data && typeof data === 'object' && !Array.isArray(data)
      ? (data as Record<string, unknown>).insight
      : null;
  const insight = normalizeBehaviorInsight(payload);
  if (!insight) {
    throw new Error('Invalid behavior insight snooze response');
  }
  return insight;
}

export async function revokeBehaviorInsight(insightId: string): Promise<BehaviorRevokeResponse> {
  const { data } = await api.post<unknown>(
    `/api/behavior/insights/${encodeURIComponent(insightId)}/revoke`,
  );
  if (!data || typeof data !== 'object' || Array.isArray(data)) {
    throw new Error('Invalid behavior insight revoke response');
  }
  const raw = data as Record<string, unknown>;
  const insight = normalizeBehaviorInsight(raw.insight);
  if (!insight) {
    throw new Error('Invalid behavior insight revoke response');
  }
  return {
    insight,
    strategy_effect_changed: Boolean(raw.strategy_effect_changed),
    profile_preference_remains_active: Boolean(raw.profile_preference_remains_active),
  };
}

export async function applyBehaviorRecommendation(
  insightId: string,
  expectedProfileRevision: number,
): Promise<LoadedProfile & { recommendationStatus: ApplyBehaviorRecommendationResponse['status']; recommendationKey: string }> {
  const { data } = await api.post<ApplyBehaviorRecommendationResponse>(
    `/api/behavior/insights/${encodeURIComponent(insightId)}/apply-recommendation`,
    { expected_profile_revision: expectedProfileRevision },
  );
  return {
    profile: normalizeProfile(data.profile as unknown as ProfileApiRecord),
    revision: data.profile_revision,
    recommendationStatus: data.status,
    recommendationKey: data.recommendation_key,
  };
}
