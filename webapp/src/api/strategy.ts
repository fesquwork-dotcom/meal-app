import { api } from '@/api/client';
import type { ResourceLoaderOptions } from '@/api/resourceLoaderOptions';
import type { CurrentStrategyResponse, StrategyByIdResponse } from '@/types/strategy';
import { normalizeDecisionExplanations } from '@/features/strategy/normalizeDecisionExplanations';
import { normalizeDecisionOutcomes } from '@/features/strategy/normalizeDecisionOutcomes';

export async function getCurrentStrategy(
  options?: ResourceLoaderOptions,
): Promise<CurrentStrategyResponse> {
  const { data } = await api.get<CurrentStrategyResponse>('/api/strategy/current', {
    signal: options?.signal,
  });
  return {
    ...data,
    decision_explanations: normalizeDecisionExplanations(data.decision_explanations),
    decision_outcomes: normalizeDecisionOutcomes(data.decision_outcomes),
  };
}

export async function getStrategyById(
  strategyId: string,
  options?: ResourceLoaderOptions,
): Promise<StrategyByIdResponse> {
  const { data } = await api.get<StrategyByIdResponse>(`/api/strategy/${strategyId}`, {
    signal: options?.signal,
  });
  return {
    ...data,
    decision_explanations: normalizeDecisionExplanations(data.decision_explanations),
    decision_outcomes: normalizeDecisionOutcomes(data.decision_outcomes),
  };
}
