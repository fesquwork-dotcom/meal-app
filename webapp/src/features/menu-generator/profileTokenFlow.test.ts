import { describe, expect, it } from 'vitest';

import {
  generationPreviewReducer,
  INITIAL_GENERATION_PREVIEW_STATE,
  isPreviewTokenExpired,
} from '@/features/menu-generator/generationPreviewReducer';
import { isProfileDraftDirty, extractProfileDraft } from '@/features/profile/profileDraft';
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

describe('profile draft persistence state', () => {
  it('detects dirty draft when proteins change', () => {
    const server = baseProfile();
    const draft = extractProfileDraft({ ...server, proteins: ['any'] });
    expect(isProfileDraftDirty(server, draft)).toBe(true);
  });

  it('keeps empty proteins as incomplete draft', () => {
    const profile = normalizeProfile({
      user_id: 1,
      first_name: '',
      days: 5,
      budget: 3000,
      proteins: [],
      goal: 'home',
      meal_types: ['breakfast', 'lunch', 'dinner'],
      meals_per_day: 3,
      persons: 2,
      cooktime: 'medium',
      dietary_constraints: [],
      store: 'any',
      updated_at: null,
    });
    expect(profile.proteins).toEqual([]);
  });
});

describe('preview token expiration', () => {
  it('detects expired preview token by expires_at', () => {
    const past = new Date(Date.now() - 60_000).toISOString();
    expect(isPreviewTokenExpired(past)).toBe(true);
  });

  it('clears preview on token expired invalidation', () => {
    const next = generationPreviewReducer(
      {
        ...INITIAL_GENERATION_PREVIEW_STATE,
        phase: 'ready',
        preview: {
          status: 'ready',
          preview_version: 1,
          strategy: null,
          explanation: null,
          conflicts: [],
          warnings: [],
          memory_summary: {
            has_applied_signals: false,
            applied_count: 0,
            ignored_count: 0,
            types: [],
          },
          preview_token: 'tok',
          preview_expires_at: '2020-01-01T00:00:00+00:00',
          memory_unavailable: false,
        },
        previewBuiltAtRevision: 0,
      },
      {
        type: 'strategy_inputs_changed',
        reason: 'preview_token_expired',
        messageKey: 'preview_expired',
      },
    );
    expect(next.phase).toBe('expired');
    expect(next.preview).toBeNull();
  });
});
