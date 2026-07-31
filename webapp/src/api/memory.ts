import { api } from '@/api/client';
import type { ResourceLoaderOptions } from '@/api/resourceLoaderOptions';
import { normalizeProfile } from '@/features/profile/normalizeProfile';
import { parseMemorySignals } from '@/features/memory/memorySignalsViewModel';
import type { LoadedProfile } from '@/api/profile';
import type { ProfileApiRecord } from '@/types/profile';
import type { MemorySignal, PromoteMemorySignalResponse } from '@/types/memory';

export async function getMemorySignals(
  options?: ResourceLoaderOptions,
): Promise<MemorySignal[]> {
  const { data } = await api.get<unknown>('/api/memory/signals', {
    signal: options?.signal,
  });
  return parseMemorySignals(data);
}

export async function confirmMemorySignal(signalId: string): Promise<void> {
  await api.post(`/api/memory/signals/${encodeURIComponent(signalId)}/confirm`);
}

export async function dismissMemorySignal(signalId: string): Promise<void> {
  await api.delete(`/api/memory/signals/${encodeURIComponent(signalId)}`);
}

export async function promoteMemorySignal(
  signalId: string,
  expectedProfileRevision: number,
): Promise<LoadedProfile & { promotionStatus: PromoteMemorySignalResponse['status'] }> {
  const { data } = await api.post<PromoteMemorySignalResponse>(
    `/api/memory/signals/${encodeURIComponent(signalId)}/promote`,
    { expected_profile_revision: expectedProfileRevision },
  );
  return {
    profile: normalizeProfile(data.profile as unknown as ProfileApiRecord),
    revision: data.profile_revision,
    promotionStatus: data.status,
  };
}
