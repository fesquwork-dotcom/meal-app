import { describe, expect, it } from 'vitest';

import {
  behaviorInsightsReducer,
  initialBehaviorInsightsState,
  mapListResponse,
} from '@/features/behavior/behaviorInsightsState';
import {
  shouldLoadResourceOnMount,
  RESOURCE_FRESHNESS_POLICIES,
} from '@/features/async-resource';
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

function loadReady(insights: BehaviorInsight[]) {
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
        insights,
        candidate_count: insights.length,
        confirmed_count: 0,
      }),
      now: 1000,
    },
  });
}

describe('behaviorFreshness', () => {
  it('fresh cache skips mount load', () => {
    const ready = loadReady([a]);
    expect(
      shouldLoadResourceOnMount(ready.resource, RESOURCE_FRESHNESS_POLICIES.behavior, 1000 + 10_000),
    ).toBe(false);
  });

  it('stale GET evaluation refreshes and can return new candidate', () => {
    const ready = loadReady([a]);
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
          insights: [a, b],
          candidate_count: 2,
          confirmed_count: 0,
        }),
      },
    });
    expect(updated.resource.data?.insights).toHaveLength(2);
  });
});
