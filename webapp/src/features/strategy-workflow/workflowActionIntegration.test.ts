import { describe, expect, it, vi } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';

import {
  classifyStrategyWorkflowError,
  workflowFailure,
  workflowSuccess,
} from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import {
  applyStrategyInputChange,
  INITIAL_STRATEGY_INPUTS_STATE,
} from '@/features/strategy-inputs/strategyInputsState';
import type { MenuPlan } from '@/types/menu';

const sampleMenu: MenuPlan = {
  summary: 'План',
  plan_start_date: '2026-07-13',
  strategy_id: 'strategy-wf',
  total_cost: 1000,
  days_plan: [],
  recipes: [],
  basket: [],
};

function axiosError(status: number, code: string) {
  return new AxiosError('x', undefined, undefined, undefined, {
    status,
    data: { code, message: 'backend' },
    headers: {},
    statusText: 'Error',
    config: { headers: new AxiosHeaders() },
  });
}

/**
 * Simulates Action → classify → WorkflowResult → state/coordinator/UI order.
 * Coordinator runs only after ok:true.
 */
function runMutatingAction<T>(
  execute: () => Promise<{ ok: true; data: T } | { ok: false; error: unknown }>,
  onSuccess: (data: T) => void,
  notify: (reason: string) => void,
  reason: string,
) {
  return execute().then((result) => {
    if (!result.ok) {
      return result;
    }
    onSuccess(result.data);
    notify(reason);
    return result;
  });
}

describe('workflowActionIntegration', () => {
  it('failure skips coordinator and preserves MenuPlan/draft/preview snapshots', async () => {
    const notify = vi.fn();
    const menuBefore = structuredClone(sampleMenu);
    const draftBefore = { dirty: true, days: 7 };
    const previewBefore = { token: 'p1', revision: 2 };
    const compareBefore = { left: 'a', right: 'b' };
    const coordinatorRevision = INITIAL_STRATEGY_INPUTS_STATE.revision;

    const result = await runMutatingAction(
      async () => workflowFailure(axiosError(502, 'STRATEGY_SAVE_FAILED')),
      () => {
        throw new Error('should not apply success');
      },
      notify,
      'profile_saved',
    );

    expect(result.ok).toBe(false);
    expect(notify).not.toHaveBeenCalled();
    expect(sampleMenu).toEqual(menuBefore);
    expect(draftBefore).toEqual({ dirty: true, days: 7 });
    expect(previewBefore).toEqual({ token: 'p1', revision: 2 });
    expect(compareBefore).toEqual({ left: 'a', right: 'b' });
    expect(INITIAL_STRATEGY_INPUTS_STATE.revision).toBe(coordinatorRevision);
  });

  it('success applies state once then notifies coordinator once', async () => {
    const notify = vi.fn((reason: string) => {
      applyStrategyInputChange(INITIAL_STRATEGY_INPUTS_STATE, reason as 'memory_confirmed');
    });
    let applied: { id: string } | null = null;
    const menuBefore = structuredClone(sampleMenu);

    const result = await runMutatingAction(
      async () => workflowSuccess({ id: 'ms_1' }),
      (data) => {
        applied = data;
      },
      notify,
      'memory_confirmed',
    );

    expect(result.ok).toBe(true);
    expect(applied).toEqual({ id: 'ms_1' });
    expect(notify).toHaveBeenCalledTimes(1);
    expect(notify).toHaveBeenCalledWith('memory_confirmed');
    expect(sampleMenu).toEqual(menuBefore);
    expect(sampleMenu.strategy_id).toBe('strategy-wf');
  });

  it('classifies errors once before forming WorkflowResult', () => {
    const err = axiosError(409, 'PROFILE_STALE');
    const classified = classifyStrategyWorkflowError(err);
    const result = { ok: false as const, error: classified };
    expect(result.error.kind).toBe('conflict');
    expect(result.error.code).toBe('PROFILE_STALE');
  });
});
