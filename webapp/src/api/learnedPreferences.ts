import { api } from '@/api/client';
import type { ResourceLoaderOptions } from '@/api/resourceLoaderOptions';
import { normalizeLearnedPreferences } from '@/features/learned-preferences/normalizeLearnedPreferences';
import type { LearnedPreferencesResult } from '@/types/learnedPreferences';

export async function getLearnedPreferences(
  options?: ResourceLoaderOptions,
): Promise<LearnedPreferencesResult> {
  const { data } = await api.get<unknown>('/api/learned-preferences', {
    signal: options?.signal,
  });
  const normalized = normalizeLearnedPreferences(data);
  if (!normalized) {
    throw new Error('Invalid learned preferences response');
  }
  return normalized;
}

export async function acceptLearnedPreference(
  preferenceId: string,
): Promise<LearnedPreferencesResult> {
  const { data } = await api.post<unknown>(
    `/api/learned-preferences/${encodeURIComponent(preferenceId)}/accept`,
  );
  const normalized = normalizeLearnedPreferences(data);
  if (!normalized) {
    throw new Error('Invalid learned preference accept response');
  }
  return normalized;
}

export async function revokeLearnedPreference(
  preferenceId: string,
): Promise<LearnedPreferencesResult> {
  const { data } = await api.post<unknown>(
    `/api/learned-preferences/${encodeURIComponent(preferenceId)}/revoke`,
  );
  const normalized = normalizeLearnedPreferences(data);
  if (!normalized) {
    throw new Error('Invalid learned preference revoke response');
  }
  return normalized;
}

/** Persist review dismiss for the current evidence cohort. No planning side effects. */
export async function dismissLearnedPreferenceReview(
  preferenceId: string,
): Promise<LearnedPreferencesResult> {
  const { data } = await api.post<unknown>(
    `/api/learned-preferences/${encodeURIComponent(preferenceId)}/dismiss-review`,
  );
  const normalized = normalizeLearnedPreferences(data);
  if (!normalized) {
    throw new Error('Invalid learned preference dismiss-review response');
  }
  return normalized;
}
