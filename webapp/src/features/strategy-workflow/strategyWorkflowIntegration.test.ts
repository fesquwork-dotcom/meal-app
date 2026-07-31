import { describe, expect, it, vi } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';

import { classifyStrategyWorkflowError } from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import { routeStaleWorkflowError } from '@/features/strategy-workflow/routeStaleWorkflowError';
import {
  applyPreviewBecameStale,
  applyStrategyInputChange,
  INITIAL_STRATEGY_INPUTS_STATE,
} from '@/features/strategy-inputs/strategyInputsState';
import { applyPreviewInvalidation } from '@/features/strategy-inputs/strategyInvalidationCoalescing';
import type { MenuPlan } from '@/types/menu';

const sampleMenu: MenuPlan = {
  summary: 'План',
  plan_start_date: '2026-07-13',
  strategy_id: 'strategy-err',
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

describe('strategy workflow integration', () => {
  it('routes stale to coordinator and does not bump revision', () => {
    const notify = vi.fn();
    const classified = classifyStrategyWorkflowError(
      axiosError(409, 'STRATEGY_PREVIEW_STALE_BEHAVIOR'),
    );
    const routed = routeStaleWorkflowError(classified, notify);
    expect(routed.routed).toBe(true);
    expect(notify).toHaveBeenCalledWith('server_stale_behavior');

    const state = applyPreviewBecameStale(
      INITIAL_STRATEGY_INPUTS_STATE,
      'server_stale_behavior',
    ).state;
    expect(state.revision).toBe(0);
  });

  it('does not route non-stale errors to coordinator', () => {
    const notify = vi.fn();
    const classified = classifyStrategyWorkflowError(axiosError(502, 'STRATEGY_SAVE_FAILED'));
    expect(routeStaleWorkflowError(classified, notify).routed).toBe(false);
    expect(notify).not.toHaveBeenCalled();
  });

  it('preserves MenuPlan and draft snapshot across error kinds', () => {
    const draft = { dirty: true, revision: 3 };
    const before = structuredClone(sampleMenu);
    for (const code of [
      'STRATEGY_PREVIEW_STALE_PROFILE',
      'REQUEST_VALIDATION_ERROR',
      'STRATEGY_SAVE_FAILED',
      'AUTH_UNAUTHORIZED',
    ]) {
      classifyStrategyWorkflowError(axiosError(code.startsWith('AUTH') ? 401 : 409, code));
      expect(sampleMenu).toEqual(before);
      expect(draft).toEqual({ dirty: true, revision: 3 });
    }
  });

  it('coalesces local invalidation then server stale without revision double bump', () => {
    let state = applyStrategyInputChange(INITIAL_STRATEGY_INPUTS_STATE, 'profile_saved').state;
    expect(state.revision).toBe(1);
    const preview = applyPreviewInvalidation(
      {
        phase: 'ready',
        preview: { token: 't' },
        activeConflict: null,
        planStartDate: '2026-07-13',
        previewBuiltAtRevision: 0,
        staleMessageKey: null,
        error: null,
      },
      'profile_saved',
    );
    state = applyPreviewBecameStale(state, 'server_stale_profile').state;
    const second = applyPreviewInvalidation(preview.next, 'server_stale_profile');
    expect(state.revision).toBe(1);
    expect(second.didReset).toBe(false);
    expect(second.coalesced).toBe(true);
  });
});
