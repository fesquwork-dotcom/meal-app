import { describe, expect, it } from 'vitest';

import { ProfileStaleConflictError } from '@/api/profile';
import { extractProfileStaleDetails } from '@/features/profile/extractProfileStaleDetails';
import { normalizeProfile } from '@/features/profile/normalizeProfile';
import type { Profile } from '@/types/profile';

function baseProfile(): Profile {
  return normalizeProfile({
    user_id: 1,
    first_name: 'Test',
    days: 5,
    budget: 3000,
    proteins: ['chicken'],
    goal: 'home',
    meal_types: ['breakfast', 'lunch', 'dinner'],
    meals_per_day: 3,
    persons: 2,
    cooktime: 'medium',
    dietary_constraints: [],
    store: 'any',
    updated_at: '2026-01-01T00:00:00Z',
  });
}

describe('extractProfileStaleDetails', () => {
  it('reads ProfileStaleConflictError', () => {
    const profile = baseProfile();
    const details = extractProfileStaleDetails(
      new ProfileStaleConflictError('stale', profile, 4),
    );
    expect(details).toEqual({ currentProfile: profile, currentRevision: 4 });
  });

  it('reads duck-typed PROFILE_STALE with currentProfile', () => {
    const profile = baseProfile();
    const details = extractProfileStaleDetails({
      code: 'PROFILE_STALE',
      currentProfile: profile,
      currentRevision: 8,
    });
    expect(details?.currentRevision).toBe(8);
    expect(details?.currentProfile.user_id).toBe(1);
  });

  it('reads axios-shaped PROFILE_STALE details envelope', () => {
    const profile = baseProfile();
    const details = extractProfileStaleDetails({
      response: {
        data: {
          code: 'PROFILE_STALE',
          details: {
            current_profile: {
              user_id: 1,
              first_name: 'Test',
              days: 5,
              budget: 3000,
              proteins: ['chicken'],
              goal: 'home',
              meal_types: ['breakfast', 'lunch', 'dinner'],
              meals_per_day: 3,
              persons: 2,
              cooktime: 'medium',
              dietary_constraints: [],
              store: 'any',
              updated_at: '2026-01-01T00:00:00Z',
            },
            current_revision: 12,
          },
        },
      },
    });
    expect(details?.currentRevision).toBe(12);
    expect(details?.currentProfile.days).toBe(profile.days);
  });

  it('returns null for malformed revision', () => {
    expect(
      extractProfileStaleDetails({
        code: 'PROFILE_STALE',
        currentProfile: baseProfile(),
        currentRevision: 'nope',
      }),
    ).toBeNull();
  });

  it('returns null when profile missing', () => {
    expect(
      extractProfileStaleDetails({
        code: 'PROFILE_STALE',
        currentRevision: 1,
      }),
    ).toBeNull();
  });

  it('returns null for unrelated errors', () => {
    expect(extractProfileStaleDetails(new Error('x'))).toBeNull();
    expect(extractProfileStaleDetails(null)).toBeNull();
  });
});
