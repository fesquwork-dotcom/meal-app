import { api } from '@/api/client';
import {
  normalizeLearningRecommendations,
  normalizeRecommendedProfilePatch,
} from '@/features/learning/normalizeLearningRecommendations';
import type {
  LearningAcceptResponse,
  LearningRecommendationSummary,
} from '@/types/learning';

export async function getLearningRecommendations(): Promise<LearningRecommendationSummary> {
  const { data } = await api.get<unknown>('/api/learning/recommendations');
  return (
    normalizeLearningRecommendations(data) ?? {
      version: 1,
      candidate_count: 0,
      accepted_count: 0,
      recommendations: [],
    }
  );
}

export async function acceptLearningRecommendation(
  recommendationId: string,
): Promise<LearningAcceptResponse> {
  const { data } = await api.post<Record<string, unknown>>(
    `/api/learning/recommendations/${encodeURIComponent(recommendationId)}/accept`,
  );
  const patch = normalizeRecommendedProfilePatch(data.recommended_profile_patch);
  if (
    data.status !== 'accepted' ||
    typeof data.recommendation_id !== 'string' ||
    !patch
  ) {
    throw new Error('Invalid learning accept response');
  }
  return {
    recommendation_id: data.recommendation_id,
    status: 'accepted',
    recommended_profile_patch: patch,
  };
}

export async function dismissLearningRecommendation(
  recommendationId: string,
): Promise<void> {
  await api.post(
    `/api/learning/recommendations/${encodeURIComponent(recommendationId)}/dismiss`,
  );
}
