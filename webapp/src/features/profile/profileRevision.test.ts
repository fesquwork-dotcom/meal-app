import { describe, expect, it } from 'vitest';

import {
  areProfileSettingsEqual,
  extractProfileDraft,
  isProfileDraftDirty,
} from '@/features/profile/profileDraft';
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

describe('profile revision comparison', () => {
  it('detects dirty draft against server profile', () => {
    const server = baseProfile();
    const draft = extractProfileDraft({ ...server, days: 7 });
    expect(isProfileDraftDirty(server, draft)).toBe(true);
  });

  it('auto-resolves equal normalized profiles', () => {
    const server = baseProfile();
    const draft = extractProfileDraft(server);
    expect(areProfileSettingsEqual(server, draft)).toBe(true);
  });
});
