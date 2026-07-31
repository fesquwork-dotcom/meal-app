import { describe, expect, it } from 'vitest';
import {
  createDefaultProfile,
  normalizeProfile,
} from '@/features/profile/normalizeProfile';
import { mealTypesFromCount } from '@/types/meal';
import type { ProfileApiRecord } from '@/types/profile';

function apiProfile(overrides: Partial<ProfileApiRecord> = {}): ProfileApiRecord {
  return {
    user_id: 1,
    first_name: '',
    budget: 3000,
    days: 5,
    meal_types: ['breakfast', 'lunch', 'dinner'],
    meals_per_day: 3,
    persons: 2,
    proteins: ['any'],
    goal: 'home',
    cooktime: 'medium',
    dietary_constraints: [],
    store: 'any',
    updated_at: null,
    ...overrides,
  };
}

describe('normalizeProfile meal_types', () => {
  it('maps legacy meals_per_day=3 to three meal types', () => {
    const profile = normalizeProfile({
      user_id: 1,
      first_name: '',
      budget: 3000,
      days: 5,
      meal_types: null,
      meals_per_day: 3,
      persons: 2,
      proteins: ['any'],
      goal: 'home',
      cooktime: 'medium',
      allergies: 'нет',
      store: 'any',
      updated_at: null,
    });

    expect(profile.meal_types).toEqual(['breakfast', 'lunch', 'dinner']);
    expect(profile.meals_per_day).toBe(3);
  });

  it('maps legacy meals_per_day=2 to breakfast and dinner', () => {
    const profile = normalizeProfile({
      user_id: 1,
      first_name: '',
      budget: 3000,
      days: 5,
      meal_types: null,
      meals_per_day: 2,
      persons: 2,
      proteins: ['any'],
      goal: 'home',
      cooktime: 'medium',
      allergies: 'нет',
      store: 'any',
      updated_at: null,
    });

    expect(profile.meal_types).toEqual(['breakfast', 'dinner']);
  });

  it('uses defaults when meal_types is empty', () => {
    const profile = createDefaultProfile(42);
    expect(profile.meal_types).toEqual(['breakfast', 'lunch', 'dinner']);
  });

  it('drops unknown meal types', () => {
    const profile = normalizeProfile({
      user_id: 1,
      first_name: '',
      budget: 3000,
      days: 5,
      meal_types: ['breakfast', 'brunch', 'dinner'],
      meals_per_day: null,
      persons: 2,
      proteins: ['any'],
      goal: 'home',
      cooktime: 'medium',
      allergies: 'нет',
      store: 'any',
      updated_at: null,
    });

    expect(profile.meal_types).toEqual(['breakfast', 'dinner']);
  });

  it('falls back to defaults when all meal types are unknown', () => {
    const profile = normalizeProfile({
      user_id: 1,
      first_name: '',
      budget: 3000,
      days: 5,
      meal_types: ['brunch'],
      meals_per_day: null,
      persons: 2,
      proteins: ['any'],
      goal: 'home',
      cooktime: 'medium',
      allergies: 'нет',
      store: 'any',
      updated_at: null,
    });

    expect(profile.meal_types).toEqual(['breakfast', 'lunch', 'dinner']);
  });

  it('keeps at least one meal type from explicit selection', () => {
    const profile = normalizeProfile({
      user_id: 1,
      first_name: '',
      budget: 3000,
      days: 5,
      meal_types: ['snack'],
      meals_per_day: null,
      persons: 2,
      proteins: ['any'],
      goal: 'home',
      cooktime: 'medium',
      allergies: 'нет',
      store: 'any',
      updated_at: null,
    });

    expect(profile.meal_types).toEqual(['snack']);
    expect(profile.meals_per_day).toBe(1);
  });
});

describe('mealTypesFromCount', () => {
  it('maps count 4+ to snack', () => {
    expect(mealTypesFromCount(4)).toEqual(['breakfast', 'lunch', 'dinner', 'snack']);
  });
});

describe('normalizeProfile dietary constraints', () => {
  it('parses legacy allergies into legacy_constraints', () => {
    const profile = normalizeProfile(
      {
        user_id: 1,
        first_name: '',
        budget: 3000,
        days: 5,
        meal_types: ['breakfast', 'lunch', 'dinner'],
        meals_per_day: 3,
        persons: 2,
        proteins: ['any'],
        goal: 'home',
        cooktime: 'medium',
        allergies: 'арахис, сельдерей',
        dietary_constraints: [],
        store: 'any',
        updated_at: null,
      },
      { legacy_constraints: ['арахис', 'сельдерей'], requires_constraint_review: true },
    );

    expect(profile.legacy_constraints).toEqual(['арахис', 'сельдерей']);
    expect(profile.requires_constraint_review).toBe(true);
    expect(profile.dietary_constraints).toEqual([]);
  });

  it('projects legacy intolerance into allergies without duplicates', () => {
    const profile = normalizeProfile(apiProfile({
      days: 5,
      budget: 3000,
      dietary_constraints: [
        { id: 'dc_1', kind: 'allergy', value: 'молоко' },
        { id: 'dc_2', kind: 'intolerance', value: 'Молоко' },
        { id: 'dc_3', kind: 'intolerance', value: 'глютен' },
      ],
    }));

    expect(profile.dietary_constraints).toEqual([
      { id: 'dc_1', kind: 'allergy', value: 'молоко' },
      { id: 'dc_3', kind: 'allergy', value: 'глютен' },
    ]);
    expect(profile.dietary_constraints.some((item) => item.kind === 'intolerance')).toBe(false);
  });
});

describe('normalizeProfile legacy limits', () => {
  it('clamps old profiles to seven days and 50,000 ₽', () => {
    const profile = normalizeProfile(apiProfile({
      days: 14,
      budget: 80_000,
    }));
    expect(profile.days).toBe(7);
    expect(profile.budget).toBe(50_000);
  });
});
