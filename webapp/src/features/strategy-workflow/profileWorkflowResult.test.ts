import { describe, expect, it, vi } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';

import { ProfileStaleConflictError } from '@/api/profile';
import { normalizeProfile } from '@/features/profile/normalizeProfile';
import { extractProfileStaleDetails } from '@/features/profile/extractProfileStaleDetails';
import {
  classifyStrategyWorkflowError,
  workflowFailure,
  workflowSuccess,
} from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import type { SaveProfileSuccess } from '@/features/strategy-workflow/workflowSuccessTypes';
import type { Profile } from '@/types/profile';
import {
  applyStrategyInputChange,
  INITIAL_STRATEGY_INPUTS_STATE,
} from '@/features/strategy-inputs/strategyInputsState';

function baseProfile(overrides: Partial<{ days: number; updated_at: string }> = {}): Profile {
  return normalizeProfile({
    user_id: 1,
    first_name: 'Test',
    days: overrides.days ?? 5,
    budget: 3000,
    proteins: ['chicken'],
    goal: 'home',
    meal_types: ['breakfast', 'lunch', 'dinner'],
    meals_per_day: 3,
    persons: 2,
    cooktime: 'medium',
    dietary_constraints: [],
    store: 'any',
    updated_at: overrides.updated_at ?? '2026-01-01T00:00:00Z',
  });
}

function axiosValidation(code: string, fieldErrors: Array<{ field: string; code: string; message: string }>) {
  return new AxiosError('x', undefined, undefined, undefined, {
    status: 422,
    data: { code, message: 'validation', field_errors: fieldErrors },
    headers: {},
    statusText: 'Unprocessable',
    config: { headers: new AxiosHeaders() },
  });
}

describe('profileWorkflowResult', () => {
  it('returns typed save success payload', () => {
    const profile = baseProfile();
    const data: SaveProfileSuccess = {
      profile,
      revision: 4,
      updatedAt: profile.updated_at,
    };
    const result = workflowSuccess(data);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.revision).toBe(4);
      expect(result.data.profile.days).toBe(5);
      expect(result.data.updatedAt).toBe(profile.updated_at);
    }
  });

  it('classifies validation failure with field errors preserved', () => {
    const err = axiosValidation('REQUEST_VALIDATION_ERROR', [
      { field: 'profile.proteins', code: 'PROFILE_PROTEIN_REQUIRED', message: 'Выберите белок.' },
    ]);
    const result = workflowFailure(err);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe('validation');
      expect(result.error.fieldErrors).toHaveLength(1);
      expect(result.error.fieldErrors[0]?.code).toBe('PROFILE_PROTEIN_REQUIRED');
    }
  });

  it('classifies PROFILE_PROTEIN_REQUIRED as validation', () => {
    const err = axiosValidation('PROFILE_PROTEIN_REQUIRED', []);
    const result = workflowFailure(err);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe('validation');
      expect(result.error.code).toBe('PROFILE_PROTEIN_REQUIRED');
    }
  });

  it('classifies PROFILE_STALE as conflict', () => {
    const server = baseProfile({ days: 7 });
    const err = new ProfileStaleConflictError('stale', server, 9);
    const classified = classifyStrategyWorkflowError(err);
    expect(classified.kind).toBe('conflict');
    expect(classified.code).toBe('PROFILE_STALE');
  });

  it('builds conflict state from typed stale details', () => {
    const server = baseProfile({ days: 7 });
    const err = new ProfileStaleConflictError('stale', server, 9);
    const details = extractProfileStaleDetails(err);
    const error = classifyStrategyWorkflowError(err);
    expect(details).not.toBeNull();
    const conflict = details ? { error, details } : null;
    expect(conflict?.details.currentRevision).toBe(9);
    expect(conflict?.details.currentProfile.days).toBe(7);
  });

  it('reload server profile result is WorkflowResult-shaped', () => {
    const profile = baseProfile();
    const result = workflowSuccess({ profile, revision: 2 });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.revision).toBe(2);
    }
  });

  it('keep-local rebase success uses SaveProfileSuccess', () => {
    const profile = baseProfile({ days: 6 });
    const result = workflowSuccess({
      profile,
      revision: 10,
      updatedAt: profile.updated_at,
    });
    expect(result.ok).toBe(true);
  });

  it('second stale replaces prior conflict details', () => {
    const first = extractProfileStaleDetails(
      new ProfileStaleConflictError('a', baseProfile({ days: 5 }), 3),
    );
    const second = extractProfileStaleDetails(
      new ProfileStaleConflictError('b', baseProfile({ days: 9 }), 11),
    );
    expect(first?.currentRevision).toBe(3);
    expect(second?.currentRevision).toBe(11);
    expect(second?.currentProfile.days).toBe(7);
  });

  it('failed save does not notify coordinator', () => {
    const notify = vi.fn();
    const result = workflowFailure(
      new ProfileStaleConflictError('stale', baseProfile(), 2),
    );
    expect(result.ok).toBe(false);
    expect(notify).not.toHaveBeenCalled();
  });

  it('successful save notifies coordinator once via profile_saved', () => {
    const before = INITIAL_STRATEGY_INPUTS_STATE;
    const after = applyStrategyInputChange(before, 'profile_saved');
    expect(after.state.revision).toBe(before.revision + 1);
    expect(after.effect.messageKey).toBe('profile_changed');
  });
});
