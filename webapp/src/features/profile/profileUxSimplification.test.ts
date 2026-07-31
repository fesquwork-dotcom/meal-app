import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

import { PROFILE_BUDGET, PROFILE_DAYS } from '@/features/profile/constants';
import { normalizeProfileDraft } from '@/features/profile/profileDraft';
import {
  COOKING_SPEED_OPTIONS,
  cookingSpeedPreferenceDescription,
} from '@/features/profile/cookingSpeedPreference';

const source = (name: string) => readFileSync(resolve(__dirname, name), 'utf-8');

describe('Sprint 10.1 profile UX contract', () => {
  it('uses aligned plan and budget limits', () => {
    expect(PROFILE_DAYS).toEqual({ min: 1, max: 7 });
    expect(PROFILE_BUDGET).toEqual({
      min: 500,
      max: 50_000,
      step: 500,
      default: 3000,
    });
  });

  it('clamps legacy local drafts on hydration', () => {
    const draft = normalizeProfileDraft({
      days: 14,
      budget: 75_000,
      meal_types: ['breakfast'],
    });
    expect(draft?.days).toBe(7);
    expect(draft?.budget).toBe(50_000);
  });

  it('removes intolerance controls and creation paths from the Profile UI', () => {
    const editor = source('DietaryConstraintsEditor.tsx');
    expect(editor).not.toContain('Непереносим');
    expect(editor).not.toContain('kind="intolerance"');
    expect(editor).not.toContain("'intolerance',");
  });

  it('uses the new human-readable speed wording on all profile screens', () => {
    const form = source('ProfileForm.tsx');
    const control = source('CookingSpeedPreferenceControl.tsx');
    expect(form).toContain('Выбирать более быстрые блюда');
    expect(form).toContain(
      'При прочих равных приложение будет чаще выбирать блюда, которые требуют меньше времени и действий.',
    );
    expect(control).toContain('Выбирать более быстрые блюда');
    expect(`${form}\n${control}`).not.toContain('Предпочтение скорости');
    expect(COOKING_SPEED_OPTIONS.find((option) => option.value === 'faster')?.label).toBe(
      'Выбирать более быстрые блюда',
    );
    expect(cookingSpeedPreferenceDescription('faster')).toContain('меньше времени и действий');
  });

  it('uses the simplified budget and period labels', () => {
    const form = source('ProfileForm.tsx');
    expect(form).toContain('Бюджет на весь план');
    expect(form).toContain('Период плана');
    expect(form).toContain('1–7 дней');
    expect(form).not.toContain('title="Бюджет"');
    expect(form).not.toContain('title="Количество дней"');
  });
});
