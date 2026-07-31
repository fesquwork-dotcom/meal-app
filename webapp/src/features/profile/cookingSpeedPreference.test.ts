import { describe, expect, it } from 'vitest';

import {
  COOKING_SPEED_OPTIONS,
  cookingPreferencesFromSpeedPreference,
  cookingSpeedPreferenceDescription,
  cookingSpeedPreferenceFromProfile,
} from '@/features/profile/cookingSpeedPreference';
import { isCookingPreferenceDirty } from '@/features/profile/profileDraft';
import { normalizeProfile } from '@/features/profile/normalizeProfile';
import {
  buildAppliedCookingSettingsViewModel,
  buildPreviewCookingPreferenceLine,
} from '@/features/strategy/appliedCookingSettingsViewModel';
import type { Profile } from '@/types/profile';

function baseProfile(overrides: Partial<Profile> = {}): Profile {
  return {
    user_id: 1,
    first_name: '',
    days: 5,
    budget: 3000,
    proteins: ['any'],
    goal: 'home',
    meal_types: ['breakfast', 'lunch', 'dinner'],
    meals_per_day: 3,
    persons: 1,
    cooktime: 'medium',
    cooking_preferences: { prefer_faster_meals: null },
    planning_preferences: { prefer_familiar_meals: null },
    dietary_constraints: [],
    legacy_constraints: [],
    requires_constraint_review: false,
    store: 'any',
    updated_at: null,
    ...overrides,
  };
}

describe('cooking speed tri-state', () => {
  it('maps null/true/false without coercion', () => {
    expect(cookingSpeedPreferenceFromProfile({ prefer_faster_meals: null })).toBe('automatic');
    expect(cookingSpeedPreferenceFromProfile({ prefer_faster_meals: true })).toBe('faster');
    expect(cookingSpeedPreferenceFromProfile({ prefer_faster_meals: false })).toBe('ignore');
  });

  it('serializes all three states for PUT', () => {
    expect(cookingPreferencesFromSpeedPreference('automatic')).toEqual({ prefer_faster_meals: null });
    expect(cookingPreferencesFromSpeedPreference('faster')).toEqual({ prefer_faster_meals: true });
    expect(cookingPreferencesFromSpeedPreference('ignore')).toEqual({ prefer_faster_meals: false });
  });

  it('exposes three options with descriptions', () => {
    expect(COOKING_SPEED_OPTIONS).toHaveLength(3);
    expect(cookingSpeedPreferenceDescription('automatic')).toContain('подтверждённые');
  });
});

describe('profile normalization tri-state', () => {
  it('normalizes missing cooking preferences to null', () => {
    const profile = normalizeProfile({
      user_id: 1,
      first_name: null,
      budget: null,
      days: null,
      meal_types: null,
      meals_per_day: null,
      persons: null,
      proteins: null,
      goal: null,
      cooktime: null,
      cooking_preferences: null,
      dietary_constraints: null,
      store: null,
      updated_at: null,
    });
    expect(profile.cooking_preferences.prefer_faster_meals).toBeNull();
  });

  it('preserves explicit false', () => {
    const profile = normalizeProfile({
      user_id: 1,
      first_name: null,
      budget: null,
      days: null,
      meal_types: null,
      meals_per_day: null,
      persons: null,
      proteins: null,
      goal: null,
      cooktime: null,
      cooking_preferences: { prefer_faster_meals: false },
      dietary_constraints: null,
      store: null,
      updated_at: null,
    });
    expect(profile.cooking_preferences.prefer_faster_meals).toBe(false);
  });
});

describe('cooking preference dirty comparison', () => {
  it('treats null and false as different', () => {
    const server = baseProfile({ cooking_preferences: { prefer_faster_meals: null } });
    const draft = {
      ...baseProfile(),
      cooking_preferences: { prefer_faster_meals: false },
      legacy_allergies: [],
    };
    expect(isCookingPreferenceDirty(server, draft)).toBe(true);
  });
});

describe('applied cooking settings view model', () => {
  it('labels memory source', () => {
    const viewModel = buildAppliedCookingSettingsViewModel({
      cooking_time_limit: 45,
      prefer_faster_meals: true,
      preference_source: 'memory',
    });
    expect(viewModel.sourceLine).toContain('подтверждённым заменам');
  });

  it('builds preview line for memory source', () => {
    const line = buildPreviewCookingPreferenceLine({
      cooking_time_limit: 45,
      prefer_faster_meals: true,
      preference_source: 'memory',
    });
    expect(line).toContain('подтверждённым');
  });
});
