import { api } from '@/api/client';
import { normalizeTrendSummary } from '@/features/trends/normalizeTrendSummary';
import type { TrendSummary } from '@/types/trends';

export async function getTrendSummary(): Promise<TrendSummary | null> {
  const { data } = await api.get<unknown>('/api/trends/summary');
  return normalizeTrendSummary(data);
}
