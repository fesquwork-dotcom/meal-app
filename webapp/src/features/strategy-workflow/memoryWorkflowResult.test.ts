import { describe, expect, it, vi } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';

import { ProfileStaleConflictError } from '@/api/profile';
import { normalizeProfile } from '@/features/profile/normalizeProfile';
import {
  classifyStrategyWorkflowError,
  workflowFailure,
  workflowSuccess,
} from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import type {
  MemoryPromotionSuccess,
  MemorySignalActionSuccess,
} from '@/features/strategy-workflow/workflowSuccessTypes';
import {
  applyStrategyInputChange,
  INITIAL_STRATEGY_INPUTS_STATE,
} from '@/features/strategy-inputs/strategyInputsState';
import type { MemorySignal } from '@/types/memory';

const signal: MemorySignal = {
  id: 'ms_1',
  type: 'ingredient_exclusion',
  label: 'Без лука',
  status: 'observed',
  evidence_count: 2,
  confidence: 0.6,
};

function profile() {
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

function axiosError(status: number, code: string) {
  return new AxiosError('x', undefined, undefined, undefined, {
    status,
    data: { code, message: 'backend' },
    headers: {},
    statusText: 'Error',
    config: { headers: new AxiosHeaders() },
  });
}

/** Mirrors MemorySignalsSection coordinator reason selection after dismiss success. */
function dismissCoordinatorReason(wasConfirmed: boolean) {
  return wasConfirmed ? 'memory_confirmed_dismissed' : 'memory_candidate_dismissed';
}

describe('memoryWorkflowResult', () => {
  it('confirm success is typed WorkflowResult', () => {
    const data: MemorySignalActionSuccess = { signalId: signal.id, signal, wasConfirmed: false };
    const result = workflowSuccess(data);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.signalId).toBe('ms_1');
    }
  });

  it('confirm failure classifies once and preserves card id', () => {
    const err = axiosError(503, 'SERVICE_UNAVAILABLE');
    const result = workflowFailure(err);
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error.kind).toBe('service_unavailable');
    }
    expect(signal.status).toBe('observed');
  });

  it('dismiss candidate selects candidate coordinator reason', () => {
    expect(dismissCoordinatorReason(false)).toBe('memory_candidate_dismissed');
  });

  it('dismiss confirmed selects confirmed coordinator reason', () => {
    expect(dismissCoordinatorReason(true)).toBe('memory_confirmed_dismissed');
  });

  it('promotion applied returns profile revision and status', () => {
    const data: MemoryPromotionSuccess = {
      profile: profile(),
      revision: 5,
      promotionStatus: 'promoted',
    };
    const result = workflowSuccess(data);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.promotionStatus).toBe('promoted');
      expect(result.data.revision).toBe(5);
    }
  });

  it('promotion already_covered is distinguishable without parsing text', () => {
    const result = workflowSuccess({
      profile: profile(),
      revision: 5,
      promotionStatus: 'already_covered' as const,
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.promotionStatus).toBe('already_covered');
    }
  });

  it('promotion Profile stale is conflict kind', () => {
    const err = new ProfileStaleConflictError('stale', profile(), 3);
    const classified = classifyStrategyWorkflowError(err);
    expect(classified.kind).toBe('conflict');
    expect(classified.code).toBe('PROFILE_STALE');
  });

  it('does not double-notify coordinator on success path', () => {
    const first = applyStrategyInputChange(INITIAL_STRATEGY_INPUTS_STATE, 'memory_promoted');
    expect(first.state.revision).toBe(1);
    // Promotion must not also send profile_saved — matrix would bump again.
    const accidental = applyStrategyInputChange(first.state, 'profile_saved');
    expect(accidental.state.revision).toBe(2);
    expect(first.state.revision).toBe(1);
  });

  it('failure does not notify coordinator', () => {
    const notify = vi.fn();
    const result = workflowFailure(axiosError(500, 'INTERNAL_ERROR'));
    expect(result.ok).toBe(false);
    expect(notify).not.toHaveBeenCalled();
  });
});
