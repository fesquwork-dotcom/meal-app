import { api } from '@/api/client';
import type { ResourceLoaderOptions } from '@/api/resourceLoaderOptions';
import type { StrategyCompareRequest, StrategyCompareResponse } from '@/types/strategyCompare';
import {
  normalizeDecisionExplanationChanges,
  normalizeDecisionExplanations,
} from '@/features/strategy/normalizeDecisionExplanations';

export async function compareStrategy(
  strategyId: string,
  request: StrategyCompareRequest = {},
  options?: ResourceLoaderOptions,
): Promise<StrategyCompareResponse> {
  const { data } = await api.post<StrategyCompareResponse>(
    `/api/strategy/${strategyId}/compare`,
    request,
    { signal: options?.signal },
  );
  return {
    ...data,
    preview: data.preview
      ? {
          ...data.preview,
          decision_explanations: normalizeDecisionExplanations(
            data.preview.decision_explanations,
          ),
        }
      : null,
    decision_changes: normalizeDecisionExplanationChanges(data.decision_changes),
  };
}
