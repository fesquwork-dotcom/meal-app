import { api } from '@/api/client';
import type { StrategyPreviewRequest } from '@/types/api';
import type {
  ResolveConflictRequest,
  ResolveConflictResponse,
  StrategyPreviewResponse,
} from '@/types/strategyPreview';
import { normalizeDecisionExplanations } from '@/features/strategy/normalizeDecisionExplanations';

export async function previewStrategy(
  request: StrategyPreviewRequest = {},
): Promise<StrategyPreviewResponse> {
  const { data } = await api.post<StrategyPreviewResponse>('/api/strategy/preview', request);
  return {
    ...data,
    decision_explanations: normalizeDecisionExplanations(data.decision_explanations),
  };
}

export async function resolveStrategyConflict(
  request: ResolveConflictRequest,
): Promise<ResolveConflictResponse> {
  const { data } = await api.post<ResolveConflictResponse>(
    '/api/strategy/resolve-conflict',
    request,
  );
  return data;
}
