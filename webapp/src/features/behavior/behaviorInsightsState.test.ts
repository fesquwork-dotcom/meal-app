import { describe, expect, it } from 'vitest';

import {
  behaviorInsightsReducer,
  initialBehaviorInsightsState,
  mapListResponse,
} from '@/features/behavior/behaviorInsightsState';
import type { BehaviorInsight } from '@/types/behavior';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';

const candidate: BehaviorInsight = {
  id: 'bi_1',
  type: 'frequent_recipe_replacement',
  status: 'candidate',
  title: 'Title',
  description: 'Description',
  evidence_count: 2,
  confidence: 0.6,
  can_confirm: true,
  can_dismiss: true,
  can_snooze: true,
  can_revoke: false,
  created_at: '2026-07-13T12:00:00+00:00',
  updated_at: '2026-07-13T12:00:00+00:00',
};

function loadReady(insights: BehaviorInsight[], requestId = 1) {
  const loading = behaviorInsightsReducer(initialBehaviorInsightsState, {
    type: 'resource',
    action: { type: 'load_started', requestId },
  });
  return behaviorInsightsReducer(loading, {
    type: 'resource',
    action: {
      type: 'load_succeeded',
      requestId,
      data: mapListResponse({
        insights,
        candidate_count: insights.filter((item) => item.status === 'candidate').length,
        confirmed_count: insights.filter((item) => item.status === 'confirmed').length,
      }),
    },
  });
}

describe('behaviorInsightsReducer', () => {
  it('starts loading from idle via resource action', () => {
    const next = behaviorInsightsReducer(initialBehaviorInsightsState, {
      type: 'resource',
      action: { type: 'load_started', requestId: 1 },
    });
    expect(next.resource.status).toBe('loading');
  });

  it('stores successful load', () => {
    const next = loadReady([candidate]);
    expect(next.resource.status).toBe('ready');
    expect(next.resource.data?.insights).toHaveLength(1);
  });

  it('stores load error without clearing when framed as refresh failure', () => {
    const ready = loadReady([candidate]);
    const refreshing = behaviorInsightsReducer(ready, {
      type: 'resource',
      action: { type: 'refresh_started', requestId: 2 },
    });
    const failed = behaviorInsightsReducer(refreshing, {
      type: 'resource',
      action: {
        type: 'refresh_failed',
        requestId: 2,
        error: classifyStrategyWorkflowError(new Error('fail')),
      },
    });
    expect(failed.resource.status).toBe('error');
    expect(failed.resource.data?.insights).toHaveLength(1);
    expect(failed.resource.error?.message).toBeTruthy();
  });

  it('marks confirm action pending for one card', () => {
    const ready = loadReady([candidate]);
    const pending = behaviorInsightsReducer(ready, {
      type: 'action_start',
      insightId: 'bi_1',
      actionType: 'confirm',
    });
    expect(pending.actionInsightId).toBe('bi_1');
    expect(pending.resource.status).toBe('ready');
  });

  it('keeps card on action error without changing resource status', () => {
    const ready = loadReady([candidate]);
    const pending = behaviorInsightsReducer(ready, {
      type: 'action_start',
      insightId: 'bi_1',
      actionType: 'dismiss',
    });
    const failed = behaviorInsightsReducer(pending, {
      type: 'action_error',
      error: {
        kind: 'conflict',
        code: 'PROFILE_STALE',
        message: 'conflict',
        fieldErrors: [],
        retryable: false,
        requiresNewPreview: false,
        requiresProfileAction: true,
        staleReason: null,
        requestId: null,
        originalStatus: 409,
      },
      insightId: 'bi_1',
    });
    expect(failed.resource.data?.insights).toHaveLength(1);
    expect(failed.resource.status).toBe('ready');
    expect(failed.actionError?.message).toBe('conflict');
    expect(failed.actionErrorsByInsightId.bi_1?.message).toBe('conflict');
    expect(failed.actionInsightId).toBeNull();
  });

  it('updates insights on confirm success', () => {
    const ready = loadReady([candidate]);
    const confirmed = behaviorInsightsReducer(ready, {
      type: 'action_success_confirm',
      insight: { ...candidate, status: 'confirmed', can_confirm: false, can_revoke: true },
    });
    expect(confirmed.resource.data?.confirmedCount).toBe(1);
    expect(confirmed.resource.data?.candidateCount).toBe(0);
  });
});
