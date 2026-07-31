import axios from 'axios';
import { api } from '@/api/client';
import type { ResourceLoaderOptions } from '@/api/resourceLoaderOptions';
import { normalizeProfile } from '@/features/profile/normalizeProfile';
import { extractProfileDraft, profileDraftToSavePayload } from '@/features/profile/profileDraft';
import type { GetProfileResponse, ProfileStaleErrorBody } from '@/types/api';
import type { Profile } from '@/types/profile';

export class ProfileStaleConflictError extends Error {
  readonly code = 'PROFILE_STALE';

  readonly currentProfile: Profile;

  readonly currentRevision: number;

  constructor(message: string, currentProfile: Profile, currentRevision: number) {
    super(message);
    this.name = 'ProfileStaleConflictError';
    this.currentProfile = currentProfile;
    this.currentRevision = currentRevision;
  }
}

export interface LoadedProfile {
  profile: Profile;
  revision: number;
}

function mapProfileResponse(data: GetProfileResponse): LoadedProfile {
  return {
    profile: normalizeProfile(data.profile, {
      legacy_constraints: data.legacy_constraints,
      requires_constraint_review: data.requires_constraint_review,
    }),
    revision: data.revision,
  };
}

export async function getProfile(options?: ResourceLoaderOptions): Promise<LoadedProfile> {
  const { data } = await api.get<GetProfileResponse>('/api/profile', {
    signal: options?.signal,
  });
  return mapProfileResponse(data);
}

export async function saveProfile(
  profile: Profile,
  expectedRevision: number,
): Promise<LoadedProfile> {
  const draft = extractProfileDraft(profile);
  try {
    const { data } = await api.put<GetProfileResponse>(
      '/api/profile',
      profileDraftToSavePayload(draft, expectedRevision),
    );
    return mapProfileResponse(data);
  } catch (err: unknown) {
    if (axios.isAxiosError(err) && err.response?.status === 409) {
      const body = err.response.data as ProfileStaleErrorBody | undefined;
      const details = body?.details;
      if (body?.code === 'PROFILE_STALE' && details?.current_profile) {
        throw new ProfileStaleConflictError(
          body.message ?? 'Настройки были изменены в другой сессии.',
          normalizeProfile(details.current_profile),
          details.current_revision,
        );
      }
    }
    throw err;
  }
}
