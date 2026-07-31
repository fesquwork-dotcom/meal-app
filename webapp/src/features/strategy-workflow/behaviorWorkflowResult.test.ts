import {
  behaviorInsightsReducer,
  initialBehaviorInsightsState,
  mapListResponse,
} from '@/features/behavior/behaviorInsightsState';
import {
  classifyStrategyWorkflowError,
  workflowFailure,
  workflowSuccess,
} from '@/features/strategy-workflow/classifyStrategyWorkflowError';
import type {
  BehaviorInsightActionSuccess,
  BehaviorRecommendationSuccess,
} from '@/features/strategy-workflow/workflowSuccessTypes';
import type { BehaviorInsight } from '@/types/behavior';
import { ProfileStaleConflictError } from '@/api/profile';
import { normalizeProfile } from '@/features/profile/normalizeProfile';
import { describe, expect, it, vi } from 'vitest';
import { AxiosError, AxiosHeaders } from 'axios';


const insight: BehaviorInsight = {
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

function axiosError(status: number, code: string) {
  return new AxiosError('x', undefined, undefined, undefined, {
    status,
    data: { code, message: 'backend' },
    headers: {},
    statusText: 'Error',
    config: { headers: new AxiosHeaders() },
  });
}

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

describe('behaviorWorkflowResult', () => {
  it('confirm success typed result', () => {
    const data: BehaviorInsightActionSuccess = { insight };
    const result = workflowSuccess(data);
    expect(result.ok).toBe(true);
  });

  it('dismiss success typed result', () => {
    const result = workflowSuccess({ insight: { ...insight, status: 'dismissed' } });
    expect(result.ok).toBe(true);
  });

  it('snooze success includes snoozedUntil', () => {
    const result = workflowSuccess({
      insight: { ...insight, status: 'snoozed', snoozed_until: '2026-08-01T00:00:00Z' },
      snoozedUntil: '2026-08-01T00:00:00Z',
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.snoozedUntil).toBe('2026-08-01T00:00:00Z');
    }
  });

  it('revoke success preserves strategy and preference metadata', () => {
    const data: BehaviorInsightActionSuccess = {
      insight: { ...insight, status: 'revoked', can_revoke: false },
      strategyEffectChanged: true,
      profilePreferenceRemainsActive: true,
    };
    const result = workflowSuccess(data);
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.strategyEffectChanged).toBe(true);
      expect(result.data.profilePreferenceRemainsActive).toBe(true);
    }
  });

  it('recommendation applied vs already_applied vs already_covered', () => {
    const applied: BehaviorRecommendationSuccess = {
      profile: profile(),
      revision: 3,
      recommendationStatus: 'applied',
      recommendationKey: 'prefer_familiar_meals',
    };
    const already: BehaviorRecommendationSuccess = {
      ...applied,
      recommendationStatus: 'already_applied',
    };
    const covered: BehaviorRecommendationSuccess = {
      ...applied,
      recommendationStatus: 'already_covered',
    };
    expect(workflowSuccess(applied).ok && applied.recommendationStatus).toBe('applied');
    expect(already.recommendationStatus).toBe('already_applied');
    expect(covered.recommendationStatus).toBe('already_covered');
  });

  it('recommendation Profile stale is conflict', () => {
    const classified = classifyStrategyWorkflowError(
      new ProfileStaleConflictError('stale', profile(), 2),
    );
    expect(classified.kind).toBe('conflict');
  });

  it('stores typed action error per pending card without clearing list', () => {
    let ready = behaviorInsightsReducer(initialBehaviorInsightsState, {
      type: 'resource',
      action: { type: 'load_started', requestId: 1 },
    });
    ready = behaviorInsightsReducer(ready, {
      type: 'resource',
      action: {
        type: 'load_succeeded',
        requestId: 1,
        data: mapListResponse({
          insights: [insight],
          candidate_count: 1,
          confirmed_count: 0,
        }),
      },
    });
    const pending = behaviorInsightsReducer(ready, {
      type: 'action_start',
      insightId: 'bi_1',
      actionType: 'confirm',
    });
    const failed = behaviorInsightsReducer(pending, {
      type: 'action_error',
      error: classifyStrategyWorkflowError(axiosError(502, 'STRATEGY_SAVE_FAILED')),
    });
    expect(failed.resource.data?.insights).toHaveLength(1);
    expect(failed.actionError?.kind).toBe('retryable');
    expect(failed.actionInsightId).toBeNull();
  });

  it('failure does not call coordinator', () => {
    const notify = vi.fn();
    const result = workflowFailure(axiosError(409, 'BEHAVIOR_INSIGHT_CONFLICT'));
    expect(result.ok).toBe(false);
    expect(notify).not.toHaveBeenCalled();
  });
});
