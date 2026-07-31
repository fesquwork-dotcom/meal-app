import { api } from '@/api/client';
import { normalizeInsightSummary } from '@/features/insights/normalizeInsightSummary';
import type { InsightSummary } from '@/types/insights';

export async function getInsightSummary(): Promise<InsightSummary | null> {
  const { data } = await api.get<unknown>('/api/insights/summary');
  return normalizeInsightSummary(data);
}

