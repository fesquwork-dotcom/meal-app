import { describe, expect, it } from 'vitest';

import {
  behaviorInsightsReducer,
  initialBehaviorInsightsState,
  mapListResponse,
} from '@/features/behavior/behaviorInsightsState';
import { classifyStrategyWorkflowError } from '@/features/strategy-workflow';
import type { BehaviorInsight } from '@/types/behavior';

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

const newer: BehaviorInsight = {
  ...candidate,
  id: 'bi_2',
  title: 'Newer',
};

function loadReady(insights: BehaviorInsight[], candidateCount: number, requestId = 1) {
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
        candidate_count: candidateCount,
        confirmed_count: 0,
      }),
    },
  });
}

describe('behaviorResourceState', () => {
  it('loads candidate and confirmed counts', () => {
    const next = loadReady([candidate], 1);
    expect(next.resource.data?.candidateCount).toBe(1);
  });

  it('empty list is ready', () => {
    const next = loadReady([], 0);
    expect(next.resource.status).toBe('ready');
    expect(next.resource.data?.insights).toEqual([]);
  });

  it('refresh returns new candidate', () => {
    const ready = loadReady([candidate], 1);
    const refreshing = behaviorInsightsReducer(ready, {
      type: 'resource',
      action: { type: 'refresh_started', requestId: 2 },
    });
    const updated = behaviorInsightsReducer(refreshing, {
      type: 'resource',
      action: {
        type: 'refresh_succeeded',
        requestId: 2,
        data: mapListResponse({
          insights: [candidate, newer],
          candidate_count: 2,
          confirmed_count: 0,
        }),
      },
    });
    expect(updated.resource.data?.insights).toHaveLength(2);
  });

  it('refresh failure preserves cards', () => {
    const ready = loadReady([candidate], 1);
    const refreshing = behaviorInsightsReducer(ready, {
      type: 'resource',
      action: { type: 'refresh_started', requestId: 2 },
    });
    const failed = behaviorInsightsReducer(refreshing, {
      type: 'resource',
      action: {
        type: 'refresh_failed',
        requestId: 2,
        error: classifyStrategyWorkflowError(new Error('down')),
      },
    });
    expect(failed.resource.data?.insights).toHaveLength(1);
  });

  it('request race keeps newer list', () => {
    let state = behaviorInsightsReducer(initialBehaviorInsightsState, {
      type: 'resource',
      action: { type: 'load_started', requestId: 1 },
    });
    state = behaviorInsightsReducer(state, {
      type: 'resource',
      action: { type: 'load_started', requestId: 2 },
    });
    state = behaviorInsightsReducer(state, {
      type: 'resource',
      action: {
        type: 'load_succeeded',
        requestId: 2,
        data: mapListResponse({
          insights: [newer],
          candidate_count: 1,
          confirmed_count: 0,
        }),
      },
    });
    state = behaviorInsightsReducer(state, {
      type: 'resource',
      action: {
        type: 'load_succeeded',
        requestId: 1,
        data: mapListResponse({
          insights: [candidate],
          candidate_count: 1,
          confirmed_count: 0,
        }),
      },
    });
    expect(state.resource.data?.insights[0]?.id).toBe('bi_2');
  });
});
