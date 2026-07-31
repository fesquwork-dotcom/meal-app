import { describe, expect, it } from 'vitest';

import {
  behaviorInsightsReducer,
  initialBehaviorInsightsState,
  mapListResponse,
} from '@/features/behavior/behaviorInsightsState';
import type { BehaviorInsight } from '@/types/behavior';

const a: BehaviorInsight = {
  id: 'bi_a',
  type: 'frequent_recipe_replacement',
  status: 'candidate',
  title: 'A',
  description: 'A',
  evidence_count: 1,
  confidence: 0.5,
  can_confirm: true,
  can_dismiss: true,
  can_snooze: true,
  can_revoke: false,
  created_at: '2026-07-13T12:00:00+00:00',
  updated_at: '2026-07-13T12:00:00+00:00',
};

const b: BehaviorInsight = { ...a, id: 'bi_b', title: 'B' };

function loadReady() {
  const loading = behaviorInsightsReducer(initialBehaviorInsightsState, {
    type: 'resource',
    action: { type: 'load_started', requestId: 1 },
  });
  return behaviorInsightsReducer(loading, {
    type: 'resource',
    action: {
      type: 'load_succeeded',
      requestId: 1,
      data: mapListResponse({
        insights: [a, b],
        candidate_count: 2,
        confirmed_count: 0,
      }),
    },
  });
}

const conflictError = {
  kind: 'conflict' as const,
  code: 'X',
  message: 'conflict',
  fieldErrors: [],
  retryable: false,
  requiresNewPreview: false,
  requiresProfileAction: false,
  staleReason: null,
  requestId: null,
  originalStatus: 409,
};

describe('perCardActionErrors', () => {
  it('isolates action errors per insight', () => {
    const ready = loadReady();
    const failedA = behaviorInsightsReducer(ready, {
      type: 'action_error',
      error: conflictError,
      insightId: 'bi_a',
    });
    expect(failedA.actionErrorsByInsightId.bi_a?.message).toBe('conflict');
    expect(failedA.actionErrorsByInsightId.bi_b).toBeUndefined();
    expect(failedA.resource.status).toBe('ready');
  });

  it('preserves unrelated card error when another fails', () => {
    let state = loadReady();
    state = behaviorInsightsReducer(state, {
      type: 'action_error',
      error: conflictError,
      insightId: 'bi_a',
    });
    state = behaviorInsightsReducer(state, {
      type: 'action_error',
      error: { ...conflictError, message: 'other' },
      insightId: 'bi_b',
    });
    expect(state.actionErrorsByInsightId.bi_a?.message).toBe('conflict');
    expect(state.actionErrorsByInsightId.bi_b?.message).toBe('other');
  });

  it('success clears only own card error', () => {
    let state = loadReady();
    state = behaviorInsightsReducer(state, {
      type: 'action_error',
      error: conflictError,
      insightId: 'bi_a',
    });
    state = behaviorInsightsReducer(state, {
      type: 'action_error',
      error: { ...conflictError, message: 'other' },
      insightId: 'bi_b',
    });
    state = behaviorInsightsReducer(state, {
      type: 'action_success_dismiss',
      insightId: 'bi_a',
    });
    expect(state.actionErrorsByInsightId.bi_a).toBeUndefined();
    expect(state.actionErrorsByInsightId.bi_b?.message).toBe('other');
  });
});
