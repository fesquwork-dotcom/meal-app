import { ProfileStaleConflictError } from '@/api/profile';
import { normalizeProfile } from '@/features/profile/normalizeProfile';
import type { ProfileStaleDetails } from '@/features/strategy-workflow/workflowSuccessTypes';
import type { ProfileApiRecord } from '@/types/profile';

function isFiniteRevision(value: unknown): value is number {
  return typeof value === 'number' && Number.isFinite(value) && value >= 0;
}

/**
 * Extracts typed Profile CAS conflict details without storing raw `details`.
 * Returns null when payload is missing or malformed.
 */
export function extractProfileStaleDetails(error: unknown): ProfileStaleDetails | null {
  if (error instanceof ProfileStaleConflictError) {
    if (!error.currentProfile || !isFiniteRevision(error.currentRevision)) {
      return null;
    }
    return {
      currentProfile: error.currentProfile,
      currentRevision: error.currentRevision,
    };
  }

  if (!error || typeof error !== 'object') {
    return null;
  }

  const candidate = error as {
    code?: unknown;
    currentProfile?: unknown;
    currentRevision?: unknown;
    response?: { data?: unknown };
  };

  if (
    candidate.code === 'PROFILE_STALE' &&
    candidate.currentProfile &&
    typeof candidate.currentProfile === 'object' &&
    isFiniteRevision(candidate.currentRevision)
  ) {
    try {
      return {
        currentProfile: normalizeProfile(candidate.currentProfile as ProfileApiRecord),
        currentRevision: candidate.currentRevision,
      };
    } catch {
      return null;
    }
  }

  const body = candidate.response?.data;
  if (!body || typeof body !== 'object') {
    return null;
  }
  const raw = body as {
    code?: unknown;
    details?: { current_profile?: unknown; current_revision?: unknown };
  };
  if (raw.code !== 'PROFILE_STALE' || !raw.details?.current_profile) {
    return null;
  }
  if (!isFiniteRevision(raw.details.current_revision)) {
    return null;
  }
  try {
    return {
      currentProfile: normalizeProfile(raw.details.current_profile as ProfileApiRecord),
      currentRevision: raw.details.current_revision,
    };
  } catch {
    return null;
  }
}
